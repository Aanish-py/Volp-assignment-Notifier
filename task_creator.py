from google_tasks.auth import get_google_tasks_service

class TaskCreator:
    def __init__(self):
        self.service = get_google_tasks_service()
