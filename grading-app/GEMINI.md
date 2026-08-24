# Literature Clock Grading App

A generic, mobile-first SvelteKit application for grading literature quotes and classifying them as AM or PM. This tool is designed to curate a dataset of literary time references for a "Literature Clock".

## Project Overview

- **Purpose:** Curate and grade literary snippets that mention specific times.
- **Framework:** SvelteKit 5 (using Svelte 5 runes/features where applicable).
- **Styling:** Tailwind CSS 4.
- **Database:** Neon Postgres (Serverless) using the `@neondatabase/serverless` driver.
- **Architecture:** 
  - **Frontend:** Mobile-first responsive UI with a card-based "Tinder-like" grading interface.
  - **Backend:** SvelteKit API routes for fetching entries, submitting votes, and retrieving statistics.

## Key Features

- **Random Entry Fetching:** Automatically retrieves the next unvoted, AI-verified literary entry.
- **Grading System:**
  - **Star Rating:** 1-5 stars for quality.
  - **AM/PM/Ambiguous:** Classification of the time reference.
  - **Deny:** Mark entries as invalid or non-literary (sets rating to 0).
- **Time Correction:** Ability to manually override the detected time in the snippet.
- **AI Integration (Pre-process):** Displays AI-generated ratings and reasoning to assist human graders.
- **Progress Tracking:** Real-time stats on total entries, voted entries, and average quality rating.

## Getting Started

### Prerequisites

- Node.js and npm installed.
- A Neon Postgres database instance.

### Installation

```bash
npm install
```

### Environment Variables

Create a `.env` file in the root directory:

```env
DATABASE_URL=postgres://user:password@ep-host.neon.tech/neondb
```

### Development

```bash
npm run dev
```

### Building for Production

```bash
npm run build
npm run preview
```

## Database Schema (Inferred)

### `entries` Table
- `id`: Primary Key
- `snippet`: The literary quote (HTML supported).
- `time_min_str`: Interval start time string (e.g. "14:30").
- `time_max_str`: Interval end time string (e.g. "14:30").
- `time_focus_str`: Interval focus time string (e.g. "14:30").
- `time_min_m`: Interval start minute of day (0..1439).
- `time_max_m`: Interval end minute of day.
- `time_focus_m`: Interval focus minute of day.
- `author`: Author of the work.
- `title`: Title of the work.
- `link`: Source link (e.g., Google Books).
- `categories`: Array of tags/categories.
- `ai_rating`: AI-suggested quality rating.
- `ai_reason`: AI's reasoning for its rating.
- `is_literature`: Boolean flag.
- `ai_checked`: Boolean flag.

### `votes` Table
- `id`: Primary Key
- `entry_id`: Foreign Key to `entries.id`.
- `rating`: Integer (0-5, where 0 is denied).
- `am_pm`: Enum (`am`, `pm`, `ambiguous`).
- `corrected_time`: Optional manual time correction.
- `created_at`: Timestamp.

## Database Initialization & Seeding

The project includes several scripts for database management:

- `seed-db.js`: Seeds the `entries` table from a JSONL file (expects a file at `../scrapers/mek_search/mek_search_results.jsonl`).
- `migrate.js`: Adds the `corrected_time` column to the `votes` table.
- `migrate_ai.js`: Adds the `ai_checked` column and an index to the `entries` table.

To initialize the database from scratch, you should run the SQL commands referenced in the README (found in `../seed.sql` relative to the project root) to create the initial table structures.

## Development Conventions

- **Component Logic:** Logic is primarily kept in `+page.svelte` for simple views, or extracted to components in `$lib/` if they become complex.
- **API Design:** All API endpoints are located in `src/routes/api/`.
- **Database Access:** Use the shared SQL client in `src/lib/server/db.js`.
- **Styling:** Use Tailwind CSS 4 utility classes. Mobile-first approach is mandatory.
- **Transitions:** Use Svelte's built-in `fade`, `fly`, and `slide` transitions for UI interactions.
- **Svelte 5:** The project uses Svelte 5 (`svelte": "^5.48.2"`). Follow Svelte 5 best practices (runes, events, etc.) when modifying components.
