import os
import sys
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

"""
Start →
  token.json exists?
      YES → load creds
      NO → login via browser

  creds valid?
      YES → proceed
      NO →
          expired + refresh_token → refresh
          else → login again

  save token →
  return API service
  
"""

SCOPES = ["https://www.googleapis.com/auth/tasks"]

def get_google_tasks_service():
    creds = None
    
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                if os.path.exists("token.json"):
                    try:
                        os.remove("token.json")
                    except:
                        pass
                creds_path = os.path.join(getattr(sys, '_MEIPASS', os.getcwd()), "credentials.json")
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            creds_path = os.path.join(getattr(sys, '_MEIPASS', os.getcwd()), "credentials.json")
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    
    return build("tasks", "v1", credentials=creds)
