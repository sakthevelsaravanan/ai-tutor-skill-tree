import matplotlib.pyplot as plt
import matplotlib.patches as patches

fig = plt.figure(figsize=(20, 14), dpi=300)
ax = fig.add_subplot(111)
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")

# Colors
HEADER_BG = "#1e293b"      # Slate 800
TABLE_BG = "#f8fafc"       # Slate 50
BORDER_COL = "#334155"     # Slate 700
TEXT_MAIN = "#0f172a"      # Slate 900
PK_COLOR = "#b45309"       # Amber 700
FK_COLOR = "#0369a1"       # Sky 700
LINE_COLOR = "#475569"     # Slate 600

def draw_table(ax, x, y, width, title, fields):
    row_height = 2.4
    header_height = 3.2
    total_height = header_height + (len(fields) * row_height)
    
    # Header
    header = patches.FancyBboxPatch(
        (x, y - header_height), width, header_height,
        boxstyle="round,pad=0.0,rounding_size=0.8",
        facecolor=HEADER_BG, edgecolor=BORDER_COL, linewidth=1.5
    )
    ax.add_patch(header)
    ax.text(x + width/2, y - header_height/2, title,
            ha="center", va="center", color="white", fontsize=10.5, fontweight="bold")
    
    # Body
    body = patches.Rectangle(
        (x, y - total_height), width, total_height - header_height,
        facecolor=TABLE_BG, edgecolor=BORDER_COL, linewidth=1.5
    )
    ax.add_patch(body)
    
    # Fields
    for i, (field_type, field_name, data_type) in enumerate(fields):
        row_y = y - header_height - (i * row_height) - row_height/2
        
        # Divider line
        if i > 0:
            ax.plot([x, x + width], [row_y + row_height/2, row_y + row_height/2],
                    color="#e2e8f0", linewidth=0.8)
        
        # Key badge
        if field_type == "PK":
            ax.text(x + 0.8, row_y, "PK", ha="left", va="center",
                    color=PK_COLOR, fontsize=8, fontweight="bold")
        elif field_type == "FK":
            ax.text(x + 0.8, row_y, "FK", ha="left", va="center",
                    color=FK_COLOR, fontsize=8, fontweight="bold")
        elif field_type == "PFK":
            ax.text(x + 0.8, row_y, "PK,FK", ha="left", va="center",
                    color="#7c3aed", fontsize=7.5, fontweight="bold")
        else:
            ax.text(x + 0.8, row_y, "   ", ha="left", va="center",
                    color=TEXT_MAIN, fontsize=8)
            
        # Field Name
        ax.text(x + 4.2, row_y, field_name, ha="left", va="center",
                color=TEXT_MAIN, fontsize=8.5,
                fontweight="bold" if "PK" in field_type else "normal")
        
        # Data Type
        ax.text(x + width - 0.8, row_y, data_type, ha="right", va="center",
                color="#64748b", fontsize=7.8, fontfamily="monospace")
        
    return {"x": x, "y": y, "w": width, "h": total_height,
            "center": (x + width/2, y - total_height/2),
            "top": (x + width/2, y),
            "bottom": (x + width/2, y - total_height),
            "left": (x, y - total_height/2),
            "right": (x + width, y - total_height/2)}

# 1. USERS
t_users = draw_table(ax, 4, 96, 26, "USERS", [
    ("PK", "user_id", "INT AUTO_INC"),
    ("", "full_name", "VARCHAR(100)"),
    ("", "email", "VARCHAR(255) UQ"),
    ("", "password_hash", "VARCHAR(255)"),
    ("", "role", "ENUM('student','inst')"),
    ("", "created_at", "TIMESTAMP")
])

# 2. SUBJECTS
t_subjects = draw_table(ax, 37, 96, 26, "SUBJECTS", [
    ("PK", "subject_id", "INT AUTO_INC"),
    ("", "subject_key", "VARCHAR(50) UQ"),
    ("", "subject_name", "VARCHAR(100)"),
    ("", "description", "TEXT"),
    ("", "is_indexed", "BOOLEAN"),
    ("FK", "created_by", "INT NULL"),
    ("", "created_at", "TIMESTAMP")
])

# 3. TEXTBOOKS
t_textbooks = draw_table(ax, 70, 96, 26, "TEXTBOOKS", [
    ("PK", "textbook_id", "INT AUTO_INC"),
    ("FK", "subject_id", "INT"),
    ("FK", "uploaded_by", "INT NULL"),
    ("", "file_name", "VARCHAR(255)"),
    ("", "chroma_collection", "VARCHAR(100)"),
    ("", "chunk_count", "INT >= 0"),
    ("", "uploaded_at", "TIMESTAMP")
])

# 4. TOPICS
t_topics = draw_table(ax, 37, 68, 26, "TOPICS", [
    ("PK", "topic_id", "INT AUTO_INC"),
    ("FK", "subject_id", "INT"),
    ("", "topic_name", "VARCHAR(100)"),
    ("", "difficulty_level", "TINYINT (1-3)"),
    ("", "visual_type", "ENUM('iframe','p5')"),
    ("", "embed_url", "TEXT"),
    ("", "created_at", "TIMESTAMP")
])

# 5. TOPIC_PREREQUISITES
t_prereqs = draw_table(ax, 70, 68, 26, "TOPIC_PREREQUISITES", [
    ("PFK", "topic_id", "INT"),
    ("PFK", "prereq_topic_id", "INT"),
    ("", "importance_weight", "TINYINT (1-5)")
])

# 6. LEARNING_SESSIONS
t_sessions = draw_table(ax, 4, 64, 26, "LEARNING_SESSIONS", [
    ("PK", "session_id", "CHAR(36) UUID"),
    ("FK", "user_id", "INT"),
    ("FK", "subject_id", "INT"),
    ("FK", "current_topic_id", "INT NULL"),
    ("", "current_stage", "ENUM (5 stages)"),
    ("", "quiz_difficulty", "TINYINT (1-3)"),
    ("", "confused_count", "INT >= 0"),
    ("", "started_at", "TIMESTAMP"),
    ("", "updated_at", "TIMESTAMP")
])

# 7. CONVERSATION_LOGS
t_logs = draw_table(ax, 4, 30, 26, "CONVERSATION_LOGS", [
    ("PK", "log_id", "INT AUTO_INC"),
    ("FK", "session_id", "CHAR(36)"),
    ("FK", "topic_id", "INT NULL"),
    ("", "role", "ENUM('user','asst')"),
    ("", "stage", "ENUM (5 stages)"),
    ("", "content", "TEXT"),
    ("", "created_at", "TIMESTAMP")
])

# 8. QUIZ_ATTEMPTS
t_quizzes = draw_table(ax, 37, 34, 26, "QUIZ_ATTEMPTS", [
    ("PK", "attempt_id", "INT AUTO_INC"),
    ("FK", "session_id", "CHAR(36)"),
    ("FK", "user_id", "INT"),
    ("FK", "topic_id", "INT"),
    ("", "difficulty_level", "TINYINT (1-3)"),
    ("", "mcq_score", "TINYINT (0-3)"),
    ("", "check_score", "TINYINT (1-5)"),
    ("", "verdict", "ENUM (3 values)"),
    ("", "attempted_at", "TIMESTAMP")
])

# 9. STUDENT_TOPIC_MASTERY
t_mastery = draw_table(ax, 70, 34, 26, "STUDENT_TOPIC_MASTERY", [
    ("PFK", "user_id", "INT"),
    ("PFK", "topic_id", "INT"),
    ("", "mastery_status", "ENUM (4 values)"),
    ("", "best_mcq_score", "TINYINT (0-3)"),
    ("", "latest_check_score", "TINYINT (1-5)"),
    ("", "total_attempts", "INT >= 0"),
    ("", "last_updated", "TIMESTAMP")
])

# Connections (Lines with Cardinality notations)
def draw_connector(p1, p2, label1="1", label2="N", label_mid="", style="-"):
    ax.annotate("", xy=p2, xytext=p1,
                arrowprops=dict(arrowstyle="-", color=LINE_COLOR, lw=1.5, ls=style))
    # Labels
    ax.text(p1[0], p1[1], f" {label1} ", color="#1e293b", fontsize=8.5, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
    ax.text(p2[0], p2[1], f" {label2} ", color="#1e293b", fontsize=8.5, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
    if label_mid:
        mid_x = (p1[0] + p2[0]) / 2
        mid_y = (p1[1] + p2[1]) / 2
        ax.text(mid_x, mid_y, label_mid, color="#475569", fontsize=7.5,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#cbd5e1", alpha=0.9))

# 1. USERS -> SUBJECTS (1:N, created_by)
draw_connector((t_users["right"][0], t_users["right"][1] + 2),
               (t_subjects["left"][0], t_subjects["left"][1] + 2),
               "1", "N", "created_by")

# 2. SUBJECTS -> TEXTBOOKS (1:N, subject_id)
draw_connector(t_subjects["right"], t_textbooks["left"], "1", "N", "has")

# 3. USERS -> TEXTBOOKS (1:N, uploaded_by)
draw_connector((t_users["top"][0] + 5, t_users["top"][1]),
               (t_textbooks["top"][0] - 5, t_textbooks["top"][1]),
               "1", "N", "uploads")

# 4. SUBJECTS -> TOPICS (1:N, subject_id)
draw_connector(t_subjects["bottom"], t_topics["top"], "1", "N", "contains")

# 5. TOPICS -> TOPIC_PREREQUISITES (Self-referencing Recursive M:N)
draw_connector((t_topics["right"][0], t_topics["right"][1] + 3),
               (t_prereqs["left"][0], t_prereqs["left"][1] + 3),
               "1", "N", "requires (target)")
draw_connector((t_topics["right"][0], t_topics["right"][1] - 3),
               (t_prereqs["left"][0], t_prereqs["left"][1] - 3),
               "1", "N", "is_prereq_for (source)")

# 6. USERS -> LEARNING_SESSIONS (1:N, user_id)
draw_connector(t_users["bottom"], t_sessions["top"], "1", "N", "initiates")

# 7. SUBJECTS -> LEARNING_SESSIONS (1:N, subject_id)
draw_connector((t_subjects["bottom"][0] - 5, t_subjects["bottom"][1]),
               (t_sessions["right"][0], t_sessions["right"][1] + 5),
               "1", "N", "subject_of")

# 8. TOPICS -> LEARNING_SESSIONS (1:N, current_topic_id)
draw_connector((t_topics["left"][0], t_topics["left"][1] + 2),
               (t_sessions["right"][0], t_sessions["right"][1] - 2),
               "1", "0..1", "current_topic")

# 9. LEARNING_SESSIONS -> CONVERSATION_LOGS (1:N, session_id)
draw_connector(t_sessions["bottom"], t_logs["top"], "1", "N", "logs")

# 10. LEARNING_SESSIONS -> QUIZ_ATTEMPTS (1:N, session_id)
draw_connector(t_sessions["bottom"], (t_quizzes["left"][0], t_quizzes["left"][1] + 3),
               "1", "N", "records")

# 11. TOPICS -> QUIZ_ATTEMPTS (1:N, topic_id)
draw_connector(t_topics["bottom"], t_quizzes["top"], "1", "N", "assesses")

# 12. TOPICS -> STUDENT_TOPIC_MASTERY (1:N, topic_id)
draw_connector((t_topics["bottom"][0] + 5, t_topics["bottom"][1]),
               (t_mastery["left"][0], t_mastery["left"][1] + 4),
               "1", "N", "tracks")

# 13. USERS -> STUDENT_TOPIC_MASTERY (M:N via mastery table)
draw_connector((t_users["bottom"][0] + 8, t_users["bottom"][1]),
               (t_mastery["top"][0] - 3, t_mastery["top"][1]),
               "1", "N", "achieves", style="--")

# Title and Legend Banner
ax.text(50, 99.2, "AI TUTOR & SKILL TREE — CROW'S FOOT ENTITY RELATIONSHIP (ER) DIAGRAM",
        ha="center", va="center", color="#0f172a", fontsize=15, fontweight="bold")
ax.text(50, 97.7, "Normalized 3NF Relational Model across 9 Tables | MySQL 8.0+ InnoDB Engine",
        ha="center", va="center", color="#475569", fontsize=10.5)

# Legend
leg_box = patches.FancyBboxPatch(
    (4, 2), 92, 4.5, boxstyle="round,pad=0.2",
    fc="#f1f5f9", ec="#cbd5e1", lw=1.2
)
ax.add_patch(leg_box)
ax.text(6, 4.25, "LEGEND:", fontweight="bold", color="#1e293b", fontsize=9, va="center")
ax.text(14, 4.25, "PK: Primary Key", color=PK_COLOR, fontweight="bold", fontsize=8.5, va="center")
ax.text(28, 4.25, "FK: Foreign Key", color=FK_COLOR, fontweight="bold", fontsize=8.5, va="center")
ax.text(42, 4.25, "PFK: Primary + Foreign Key (Composite)", color="#7c3aed", fontweight="bold", fontsize=8.5, va="center")
ax.text(66, 4.25, "1 : N : One-to-Many Relationship", color="#334155", fontsize=8.5, va="center")
ax.text(84, 4.25, "-- : Associative Entity Link", color="#475569", fontsize=8.5, va="center")

plt.tight_layout()
plt.savefig("docs/er_diagram.png", bbox_inches="tight", dpi=300)
print("Saved docs/er_diagram.png successfully!")
