-- FTS (preferred). Use :palabra as a parameter from your client/script.
SELECT c.url, c.title
FROM courses_fts f
JOIN courses c ON c.course_id = f.rowid
WHERE courses_fts MATCH :palabra;

-- Fallback with LIKE (if you can't use FTS for some reason)
SELECT url, title
FROM courses
WHERE lower(title)         LIKE '%' || lower(:palabra) || '%'
   OR lower(description)   LIKE '%' || lower(:palabra) || '%'
   OR lower(category)      LIKE '%' || lower(:palabra) || '%'
   OR lower(value_proposal)LIKE '%' || lower(:palabra) || '%'
   OR lower(tutoria)       LIKE '%' || lower(:palabra) || '%';
