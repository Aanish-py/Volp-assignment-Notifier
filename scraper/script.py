import json
import os
from dotenv import load_dotenv
import asyncio
from playwright.async_api import async_playwright

# Load dotenv
load_dotenv()

async def scrape_assignments(email=None, password=None, portal_url=None):
    if not email:
        email = os.getenv("PORTAL_USER") or os.getenv("VOLP_EMAIL") or ""
    if not password:
        password = os.getenv("PORTAL_PASS") or os.getenv("VOLP_PASSWORD") or ""
    if not portal_url:
        portal_url = os.getenv("PORTAL_URL") or "https://classroom.volp.in"

    if not email or not password:
        print("Error: Portal Username or Password not configured in settings.")
        return []

    async with async_playwright() as p:
        print("Starting Playwright Scraper...")
        browser = await p.chromium.launch(channel="msedge", headless=False)           # Launching Browser
        page = await browser.new_page()
        
        try:
            await page.goto(portal_url)
            await page.wait_for_load_state("networkidle")
            
            # Use dynamic credentials
            await page.fill("#input-8", email)     # Logging in VOLP
            await page.fill("#input-12", password)
            await page.click("button:has-text('SIGN IN')")

            await page.wait_for_load_state("networkidle")
            await page.wait_for_selector(".course-name")                # Gathering All User Courses Element
            courses = await page.query_selector_all(".course-name")

            course_names = []
            for course in courses:                                    
                name = await course.inner_text()                        # Extracting text from each course Element
                course_names.append(name)

            print("User courses found:", course_names)

            all_assignments = []
            for i in range(len(courses)): 
                view_buttons = await page.query_selector_all(".btn-view-course")
                await view_buttons[i].click()
                await page.wait_for_load_state("networkidle")
                print(f"Course {course_names[i]} loaded successfully")
                
                await page.click("text=ASSIGNMENT")                                 # Opening "Assignments" Tab of the course
                await page.wait_for_load_state("networkidle")
                
                await page.wait_for_selector("label:has-text('Topic')", timeout=15000)
                await page.click("label:has-text('Topic')")
                links = []
                try:
                    await page.wait_for_load_state("networkidle")
                    await page.wait_for_selector(".link-router2", timeout=15000)
                    links = await page.query_selector_all(".link-router2")
                except:
                    await page.goto("https://classroom.volp.in/learner/my-courses#")
                    await page.wait_for_load_state("networkidle")
                    continue

                print(f"Found {len(links)} links") 

                pending = []                                                       
                for link in links:
                    text = await link.inner_text()                                 # Check and store Pending Assignment Links
                    print(f"Link text: '{text}'")
                    if text.startswith("0/"):
                        pending.append(link)
                    
                for j in range(len(pending)): 
                    await page.wait_for_selector(".link-router2", timeout=15000)
                    links = await page.query_selector_all(".link-router2")
                    print("Links fetched")
                    current_pending = []
                    for link in links:
                        text = await link.inner_text()
                        if text.strip().startswith("0/"):
                            current_pending.append(link)                                      # Opening Each Assignment and Extracting details         
                    await current_pending[j].click()
                    await page.wait_for_load_state("networkidle")
                    await page.wait_for_selector(".crs")
                    await page.wait_for_selector(".name")
                    await page.wait_for_selector(".textd")
                    course_el = await page.query_selector(".crs")
                    name_el = await page.query_selector(".name")
                    date_el = await page.query_selector(".textd")
                    
                    course_text = await course_el.inner_text()
                    name_text = await name_el.inner_text()
                    date_text = await date_el.inner_text()

                    # Clean data for GUI use and API compatibility
                    clean_course = course_text.replace("Course :", "").strip()
                    clean_title = name_text.replace("Assignment Name :", "").strip()
                    clean_deadline = date_text.replace("Due Date :", "").strip()

                    assignment = {
                        "course": course_text,
                        "Assignment name": name_text,                
                        "Due Date": date_text,
                        # For GUI display Compatibility
                        "title": clean_title,
                        "deadline": clean_deadline
                    }
                    print("Scraped assignment:", assignment)
                    all_assignments.append(assignment)
                    
                    await page.click(".mdi-keyboard-backspace")
                    await page.wait_for_load_state("networkidle")
                    
                    # check if topic label exists at all
                    topic = await page.query_selector("label:has-text('Topic')")
                    if topic:
                        checkbox = await page.query_selector("input[role='checkbox']")
                        is_checked = await checkbox.get_attribute("aria-checked")
                        if is_checked == "true":
                            await page.click("label:has-text('Topic')")
                            await page.wait_for_load_state("networkidle")
                
                await page.goto("https://classroom.volp.in/learner/my-courses#")
                await page.wait_for_load_state("networkidle")
            
            return all_assignments

        finally:
            await browser.close()
            print("Scraper run completed.")

if __name__ == "__main__":
    res = asyncio.run(scrape_assignments())
    with open("assignments.json", "w") as f:
        json.dump(res, f, indent=2)
    print("Done")