import base64
import io
import os
from PIL import Image

from google.cloud import aiplatform
from google.cloud.aiplatform.gapic.schema import predict
from google.cloud import storage
from google.cloud import vision

from google.oauth2 import service_account

from googleapiclient.discovery import build

SPREADSHEET_ID = '1he-XdGI69LimHrbeUxnaZEmJKm9duhBHiScTNdFB0PQ'
STORAGE_BUCKET = 'vertexai-weightcheck'
GOOGLE_CLOUD_PROJECT_ID = '418919149278'
GOOGLE_CLOUD_REGION = 'us-central1'
GOOGLE_CLOUD_AI_ENDPOINT = 'us-central1-aiplatform.googleapis.com'
GOOGLE_CLOUD_AI_ENDPOINT_ID = '6798258404306452480'

def get_sheets_data():
    # Get data from the spreadsheet
    sheet = build('sheets', 'v4').spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="Sheet1!A2:D").execute()
    values = result.get('values', [])

    # Reformat to a dictionary with image names as keys
    return dict( (x[0], [i] + x[1:]) for i, x in enumerate(values) )

def append_to_sheet(image_name, image_date, weight, note):
    sheet = build('sheets', 'v4').spreadsheets()
    return sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range="Sheet1!A2:D",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={ 'values': [[image_name, image_date, weight, note]]}).execute()

def get_image_list():
    from google.cloud import storage

    storage_client = storage.Client()
    blobs = storage_client.list_blobs('vertexai-weightcheck', prefix='dataset/')

    return [blob.name.split('/')[-1] for blob in blobs][1:] # The first result is just 'dataset/', so ignore that.

def get_image(name):
    storage_client = storage.Client()
    bucket = storage_client.bucket(STORAGE_BUCKET)
    blob = bucket.blob('dataset/' + name)
    contents = blob.download_as_string()
    return contents

def get_image_date(image_content):
    img = Image.open(io.BytesIO(image_content))
    return img._getexif()[36867]

def get_boundingbox(image_content):
    client = aiplatform.gapic.PredictionServiceClient(
        client_options={"api_endpoint": GOOGLE_CLOUD_AI_ENDPOINT})

    encoded_content = base64.b64encode(image_content).decode("utf-8")
    while len(encoded_content) > 1500000: # The API only accepts images that are <1.5M
        img = Image.open(io.BytesIO(image_content))
        width, height = img.size
        byte_io = io.BytesIO()
        img.resize((int(width/2), int(height/2))).save(byte_io, 'jpeg')
        image_content = byte_io.getvalue()
        encoded_content = base64.b64encode(image_content).decode("utf-8")

    instance = predict.instance.ImageObjectDetectionPredictionInstance(content=encoded_content).to_value()
    parameters = predict.params.ImageObjectDetectionPredictionParams(confidence_threshold=0.5, max_predictions=5).to_value()
    endpoint = client.endpoint_path(
        project=GOOGLE_CLOUD_PROJECT_ID, location=GOOGLE_CLOUD_REGION, endpoint=GOOGLE_CLOUD_AI_ENDPOINT_ID)

    response = client.predict(endpoint=endpoint, instances=[instance], parameters=parameters)

    bboxes = response.predictions[0]['bboxes']
    return len(bboxes) and bboxes[0] or [0, 0, 0, 0]

def get_cropped_image(image_content, xmin, xmax, ymin, ymax):
    img = Image.open(io.BytesIO(image_content))
    cropped = img.crop((xmin * img.width, ymin * img.height, xmax * img.width, ymax * img.height))
    byte_io = io.BytesIO()
    cropped.save(byte_io, 'jpeg')
    return byte_io.getvalue()

def get_weight(cropped_content, file_path = None):
    if file_path:
        with io.open(file_path, 'rb') as image_file:
            cropped_content = image_file.read()

    image = vision.Image(content=cropped_content)

    client = vision.ImageAnnotatorClient()
    response = client.text_detection(image=image)
    texts = response.text_annotations

    for text in texts:
        try:
            weight = float(text.description)
            if weight > 100 and weight < 200:
                return weight, ''
        except ValueError:
            pass

    if response.error.message:
        raise Exception(
            '{}\nFor more info on error messages, check: '
            'https://cloud.google.com/apis/design/errors'.format(
                response.error.message))

    return 0, str([t.description for t in texts])

if __name__ == "__main__":
    # Get the list of images in Cloud Storage
    image_list = get_image_list()

    # Get the existing info in the spreadsheet
    sheets_data = get_sheets_data()

    # Process each image
    for image_name in image_list:
        print('Processing: ' + image_name)

        if image_name in sheets_data:
            print('Skip')
            continue

        # Get image contents
        image_content = get_image(image_name)

        # Get image date
        image_date = get_image_date(image_content).replace(':', '-', 2)
        print ('Image date: ' + image_date)

        # Get its bounding box
        xmin, xmax, ymin, ymax = get_boundingbox(image_content)

        weight = 0
        note = ''

        if (xmin, xmax, ymin, ymax) == (0,0,0,0):
            # If nothing was matched, then skip
            note = 'No bounding box found'

        else:
            # Extract the image in the bounding box
            cropped_content = get_cropped_image(image_content, xmin, xmax, ymin, ymax)

            # Get text from the cropped image
            weight, note = get_weight(cropped_content)

            # If weight was not read properly, save a copy of the cropped image and write error message
            if weight == 0:
                img = Image.open(io.BytesIO(cropped_content))
                img.save('%s/%s-cropped.jpg' % (os.getcwd(), image_name.split('.')[0]))
                note = 'Weight not detected correctly: ' + note
                weight = 0

        # Update spreadsheet
        append_to_sheet(image_name, image_date, weight, note)