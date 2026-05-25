import os
import json
import asyncio
from dotenv import load_dotenv
from scraper.script import scrape_assignments
from google_tasks.auth import get_google_tasks_service
from google_tasks.creator import create_task



def run_check():
    # Load dotenv from current environment
    load_dotenv(override=True)
    
    # 1. Scrape assignments
    print("Running VIT classroom scraper...")
    new_assignments = asyncio.run(scrape_assignments())
    print(f"Scraped {len(new_assignments)} pending assignments.")
    
    # Load old assignments to identify new additions
    old_assignments = []
    if os.path.exists("assignments.json"):
        try:
            with open("assignments.json", "r") as f:
                content = f.read().strip()
                if content:
                    old_assignments = json.loads(content)
        except Exception as e:
            print(f"Error loading old assignments: {e}")
            
    # We will identify if an assignment is new by comparing key details: Course and Assignment Name
    def get_key(a):
        return (a.get("course", "").strip(), a.get("Assignment name", "").strip())
        
    old_keys = {get_key(a) for a in old_assignments}
    
    # Save the scraped list to latest_scrape.json and assignments.json
    with open("latest_scrape.json", "w") as f:
        json.dump(new_assignments, f, indent=2)
    with open("assignments.json", "w") as f:
        json.dump(new_assignments, f, indent=2)
        
    # Get Google Tasks Service if credentials exist
    service = None
    if os.path.exists("credentials.json"):
        try:
            service = get_google_tasks_service()
        except Exception as e:
            print(f"Google Tasks authentication failed/skipped: {e}")
            
    # Process new assignments
    for a in new_assignments:
        key = get_key(a)
        if key not in old_keys:
            print(f"New assignment detected: {a.get('Assignment name')}")
            # Create Google Task
            if service:
                try:
                    create_task(service, a)
                except Exception as e:
                    print(f"Error creating Google Task: {e}")

            
    print("Run check completed successfully.")

def main():
    run_check()

if __name__ == "__main__":
    main()