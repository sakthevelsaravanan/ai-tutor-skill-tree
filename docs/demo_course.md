Database foundations — original demonstration material for this project.
These notes are sample course content, not an imported textbook.

## Keys and relationships

A primary key uniquely identifies each row in a table. A primary key cannot contain null values. A composite primary key uses more than one column; for example, a student's mastery record can be identified by the pair of student ID and topic ID. A foreign key references a key in another table and prevents references to missing rows. In a learning application, each quiz attempt references its learning session and topic. Referential actions such as ON DELETE CASCADE can remove dependent records when their parent is deleted. Choose cascading deletion only when the child record should not exist independently of its parent.

## Normalization

Normalization organizes relational data to reduce duplication and update anomalies. First normal form requires each cell to hold a single value of its defined type. Second normal form requires every non-key attribute to depend on the whole of each candidate key, rather than just part of a composite key. Third normal form removes inappropriate transitive dependencies between non-key attributes. For example, store a subject's name in SUBJECTS and reference its ID from TOPICS, rather than repeating the subject name in every topic row. Normalization protects consistency, while deliberate denormalization may sometimes improve measured query performance at the cost of additional maintenance.

## Transactions and isolation

A transaction groups database operations into one unit of work. Atomicity means all operations commit together or none do. Consistency means committed changes preserve declared constraints. Isolation controls what concurrent transactions can observe. Durability means a committed change survives a database restart. PostgreSQL's default Read Committed isolation gives each statement a snapshot of committed data. SELECT FOR UPDATE locks selected rows until transaction completion. When recording a learning assessment, lock the session row, insert the attempt, let the trigger update mastery, and update the session stage in the same transaction. A rollback reverses every relational change in that transaction.

## Indexes and query planning

An index helps the database locate rows without scanning the entire table. B-tree indexes support equality and range predicates and can help ordered retrieval. Composite index column order matters: an index on user ID and topic ID can efficiently locate a user's mastery record for a topic. Indexes consume space and add maintenance work to inserts, updates, and deletes. Use EXPLAIN to inspect a query plan, and use EXPLAIN ANALYZE carefully because it executes the statement. Compare actual execution time and row counts before deciding whether an index improves the workload.
