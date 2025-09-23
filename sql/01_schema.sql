PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS courses (
  course_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  url              TEXT UNIQUE NOT NULL,
  title            TEXT NOT NULL,
  category         TEXT,
  modality         TEXT,
  duration         TEXT,
  price            TEXT,
  start_date       TEXT,
  location         TEXT,
  value_proposal   TEXT,
  tutoria          TEXT,
  description      TEXT,
  raw_html         TEXT,
  last_crawled_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_courses_url ON courses(url);

CREATE VIRTUAL TABLE IF NOT EXISTS courses_fts
USING fts5(
  title, description, category, value_proposal, tutoria,
  content='courses', content_rowid='course_id'
);

CREATE TRIGGER IF NOT EXISTS courses_ai AFTER INSERT ON courses BEGIN
  INSERT INTO courses_fts(rowid, title, description, category, value_proposal, tutoria)
  VALUES (new.course_id, new.title, new.description, new.category, new.value_proposal, new.tutoria);
END;

CREATE TRIGGER IF NOT EXISTS courses_ad AFTER DELETE ON courses BEGIN
  INSERT INTO courses_fts(courses_fts, rowid, title, description, category, value_proposal, tutoria)
  VALUES ('delete', old.course_id, old.title, old.description, old.category, old.value_proposal, old.tutoria);
END;

CREATE TRIGGER IF NOT EXISTS courses_au AFTER UPDATE ON courses BEGIN
  INSERT INTO courses_fts(courses_fts, rowid, title, description, category, value_proposal, tutoria)
  VALUES ('delete', old.course_id, old.title, old.description, old.category, old.value_proposal, old.tutoria);
  INSERT INTO courses_fts(rowid, title, description, category, value_proposal, tutoria)
  VALUES (new.course_id, new.title, new.description, new.category, new.value_proposal, new.tutoria);
END;

CREATE TABLE IF NOT EXISTS terms (
  term_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  term      TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS synonyms (
  synonym_id INTEGER PRIMARY KEY AUTOINCREMENT,
  term_id    INTEGER NOT NULL,
  synonym    TEXT NOT NULL,
  FOREIGN KEY(term_id) REFERENCES terms(term_id) ON DELETE CASCADE
);
