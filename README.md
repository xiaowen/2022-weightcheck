This is a project to try out some Google Cloud AI/ML features.  Read more about it in [this blog post](https://xiaowenx.medium.com/creating-a-smart-scale-with-google-cloud-vertex-ai-ac390793ba56).

The program herein currently uses a combination of [Vertex AI](https://cloud.google.com/vertex-ai) and [Cloud Vision](https://cloud.google.com/vision/docs/ocr) APIs to read the values from a series of images containing a scale showing a weight.  This is then written to a [Google Sheets](https://www.google.com/sheets/about/) spreadsheet and can be used to plot weight over time.

The main code is in `main.py`.  To run it, configure the environment as follows:
1. (Optional) set up Python [venv](https://docs.python.org/3/library/venv.html).  If you're using an IDE, then configure it to use this new environment (set `pythonPath` for vscode and friends).
2. Install Python libraries (`pip3 install`): `google-cloud-storage` `google-api-python-client` `google-auth-httplib2` `google-auth-oauthlib` `google-cloud-aiplatform` `google-cloud-vision` `Pillow`.
3. Configure authentication.  If using a key file, then set `GOOGLE_APPLICATION_CREDENTIALS`.  If using vscode and friends, then use `env` to set it.