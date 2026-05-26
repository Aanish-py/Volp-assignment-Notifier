from datetime import datetime

def create_task(service, assignment):
    # clean up the date string
    raw_date = assignment["Due Date"].replace("Due Date :", "").strip()
    
    due = None
    
    # try manual parse — split date and ignore time format issues
    try:
        parts = raw_date.split(" ")
        date_part = parts[0]  # "21/04/2026"
        dt = datetime.strptime(date_part, "%d/%m/%Y")
        due = dt.strftime("%Y-%m-%dT00:00:00.000Z")
    except:
        print(f"Could not parse date: {raw_date}")

    # clean up course name
    course = assignment["course"].replace("Course :", "").strip()

    task = {
        "title": f"[{course}] {assignment['Assignment name']}",
        "due": due,
        "notes": f"Due: {raw_date}"
    }

    result = service.tasks().insert(tasklist="@default", body=task).execute()
    print(f" Created: {result['title']}")


def create_all_tasks(service, assignments):
    print(f"Creating {len(assignments)} tasks...")
    for assignment in assignments:
        create_task(service, assignment)
    print("All tasks created!")