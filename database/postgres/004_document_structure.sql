-- Keep source locations separate from semantic difficulty.
ALTER TABLE topics ADD COLUMN source_file text;
ALTER TABLE topics ADD COLUMN start_page integer;
ALTER TABLE topics ADD COLUMN end_page integer;
ALTER TABLE topics ADD COLUMN sort_order integer NOT NULL DEFAULT 0;
ALTER TABLE topic_prerequisites ADD COLUMN basis text NOT NULL DEFAULT 'curated'
 CHECK (basis IN ('curated','book_order'));
