---
name: moodle
description: Use when the user asks about Moodle courses, assignments, deadlines, announcements, or calendar events. Orchestrates the Moodle MCP tools to fetch and format the requested data.
---

# Moodle Assistant Skill

When the user asks about their Moodle data (courses, assignments, deadlines, announcements, etc.), use the tools provided by the **Moodle MCP Server**. 

Follow these guidelines to provide perfect, structured responses.

## 1. Tool Selection

*   **"What are my courses?", "Show my courses"** -> `get_courses()`
*   **"What are my deadlines?", "Upcoming events?", "Calendar?"** -> `get_calendar(days_ahead=30)` (or adjust `days_ahead` based on the request).
*   **"Show assignments for [Course ID / Course Name]", "What's pending?"** -> `get_assignments(course_id="...")`. Note: if the user provides a course name instead of an ID, first call `get_courses()` to find the matching course ID, then call `get_assignments()`.
*   **"Any announcements?", "What's new?"** -> `get_announcements()`.
*   **"Show me the syllabus for [Course]", "Course details"** -> `get_course(course_id="...")`. First resolve the course ID via `get_courses()` if not provided.
*   **"Who is in my class?", "Show participants"** -> `get_participants(course_id="...")`.

## 2. Authentication Check

The MCP server connects to an existing Playwright browser session authenticated via CAS SSO. 
If any tool throws an error about the session being expired or not authenticated:
1. Stop execution.
2. Instruct the user to run the interactive login script: `python scripts/login.py`.
3. Wait for the user to confirm they have logged in before retrying the tool.

## 3. Formatting Guidelines

When presenting the data returned by the MCP tools, always use clean, structured Markdown:

*   **Group by Course:** If returning assignments or events for multiple courses, group them under Course Name headers (`### [Course Name]`).
*   **Highlight Deadlines:** Emphasize due dates in bold. If the parsed `date` or `due_date` is `null`/`None`, rely on `date_raw` or `due_date_raw` to show the human-readable string (e.g., "Tomorrow, 11:59 PM").
*   **Include Links:** Make titles clickable markdown links using the provided `url` field from the tool response. For example: `[Mini project 1](https://...)`.
*   **Statuses:** Display assignment or grade statuses clearly (e.g., ✅ Submitted, ❌ No submission).

## Example Workflows

**User: "What are my upcoming deadlines?"**
1. Call `get_calendar(days_ahead=30)`.
2. Group the resulting events by `course`.
3. Print a formatted summary showing the event `title` (linked to `url`), `date_raw`, and `course`.

**User: "Show my assignments for Automata Theory"**
1. Call `get_courses()`.
2. Find the ID for "Automata Theory" (e.g., `5776`).
3. Call `get_assignments(course_id="5776")`.
4. Output a formatted list of assignments with `due_date_raw` and `status`.

## Warning
Never ask the user for their Moodle password. The entire system relies on the local Playwright session initialized by `scripts/login.py`.