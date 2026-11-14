import matplotlib.pyplot as plt
import matplotlib.patches as patches

# ==============================================================================
# PHYSICAL RELATIONAL SCHEMA DIAGRAM GENERATOR
# Standard Relational Mapping Notation:
# - Tables with Attribute Columns & Data Types
# - PK (Primary Key) and FK (Foreign Key) badges
# - Directional reference arrows pointing from Foreign Key -> Referenced Primary Key
# ==============================================================================

fig = plt.figure(figsize=(24, 15), dpi=300)
ax = fig.add_subplot(111)
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")

# Colors
HEADER_BG = "#0f172a"      # Dark Slate 900
TABLE_BG = "#ffffff"       # Pure white
BORDER_COL = "#334155"     # Slate 700
TEXT_MAIN = "#0f172a"      # Slate 900
PK_COLOR = "#b45309"       # Amber 700
FK_COLOR = "#0284c7"       # Sky 600
PFK_COLOR = "#7c3aed"      # Purple 600
ARROW_COLOR = "#ea580c"    # Orange 600
DIVIDER_COL = "#e2e8f0"

def draw_table(ax, x, y, width, title, fields):
    row_height = 2.1
    header_height = 3.2
    total_height = header_height + (len(fields) * row_height)
    
    # Header
    header = patches.FancyBboxPatch(
        (x, y - header_height), width, header_height,
        boxstyle="round,pad=0.0,rounding_size=0.6",
        facecolor=HEADER_BG, edgecolor=BORDER_COL, linewidth=1.5, zorder=3
    )
    ax.add_patch(header)
    ax.text(x + width/2, y - header_height/2, title,
            ha="center", va="center", color="white", fontsize=10, fontweight="bold", zorder=4)
    
    # Body
    body = patches.Rectangle(
        (x, y - total_height), width, total_height - header_height,
        facecolor=TABLE_BG, edgecolor=BORDER_COL, linewidth=1.5, zorder=2
    )
    ax.add_patch(body)
    
    # Fields
    field_coords = {}
    for i, (field_type, field_name, data_type) in enumerate(fields):
        row_y = y - header_height - (i * row_height) - row_height/2
        field_coords[field_name] = (x, row_y, width)
        
        # Divider line
        if i > 0:
            ax.plot([x, x + width], [row_y + row_height/2, row_y + row_height/2],
                    color=DIVIDER_COL, linewidth=0.8, zorder=3)
        
        # Key badge
        badge_text = field_type
        badge_color = TEXT_MAIN
        if field_type == "PK":
            badge_color = PK_COLOR
        elif field_type == "FK":
            badge_color = FK_COLOR
        elif field_type == "PFK":
            badge_color = PFK_COLOR
            badge_text = "PK,FK"
            
        ax.text(x + 0.6, row_y, badge_text, ha="left", va="center",
                color=badge_color, fontsize=7.5, fontweight="bold", zorder=4)
            
        # Field Name
        ax.text(x + 3.8, row_y, field_name, ha="left", va="center",
                color=TEXT_MAIN, fontsize=8.0,
                fontweight="bold" if "PK" in field_type else "normal", zorder=4)
        
        # Data Type
        ax.text(x + width - 0.6, row_y, data_type, ha="right", va="center",
                color="#64748b", fontsize=7.5, fontfamily="monospace", zorder=4)
        
    return {
        "x": x, "y": y, "width": width, "total_height": total_height,
        "fields": field_coords,
        "left": (x, y - total_height/2),
        "right": (x + width, y - total_height/2),
        "top": (x + width/2, y),
        "bottom": (x + width/2, y - total_height)
    }

def draw_fk_arrow(p_start, p_end, connection_style="arc3,rad=0.0", label=""):
    """Draws a directed arrow from Foreign Key to Primary Key."""
    ax.annotate(
        "", xy=p_end, xytext=p_start,
        arrowprops=dict(
            arrowstyle="-|>",
            color=ARROW_COLOR,
            lw=1.5,
            connectionstyle=connection_style
        ),
        zorder=5
    )
    if label:
        mid_x = (p_start[0] + p_end[0]) / 2
        mid_y = (p_start[1] + p_end[1]) / 2
        ax.text(mid_x, mid_y, label, fontsize=7.5, fontweight="bold",
                color="#c2410c", bbox=dict(boxstyle="round,pad=0.15", fc="#ffedd5", ec="none", alpha=0.9), zorder=6)

# ==============================================================================
# TABLE DEFINITIONS
# ==============================================================================

# 1. USERS
f_users = [
    ("PK",  "user_id",       "INTEGER IDENTITY"),
    ("  ",  "full_name",     "VARCHAR(100)"),
    ("  ",  "email",         "VARCHAR(255) UNIQUE"),
    ("  ",  "password_hash", "TEXT"),
    ("  ",  "role",          "VARCHAR(20) CHECK"),
    ("  ",  "created_at",    "TIMESTAMPTZ")
]
t_users = draw_table(ax, 3, 93, 20, "USERS", f_users)

# 2. SUBJECTS
f_subjects = [
    ("PK",  "subject_id",   "INTEGER IDENTITY"),
    ("  ",  "subject_key",  "VARCHAR(50) UNIQUE"),
    ("  ",  "subject_name", "VARCHAR(100)"),
    ("  ",  "description",  "TEXT"),
    ("  ",  "is_indexed",   "BOOLEAN"),
    ("FK",  "created_by",   "INTEGER REFERENCES"),
    ("  ",  "created_at",   "TIMESTAMPTZ")
]
t_subjects = draw_table(ax, 28, 93, 21, "SUBJECTS", f_subjects)

# 3. TOPICS
f_topics = [
    ("PK",  "topic_id",         "INTEGER IDENTITY"),
    ("FK",  "subject_id",       "INTEGER REFERENCES"),
    ("  ",  "topic_name",       "VARCHAR(100)"),
    ("  ",  "difficulty_level", "SMALLINT (1-3)"),
    ("  ",  "source_file",      "TEXT"),
    ("  ",  "start_page",       "INTEGER"),
    ("  ",  "end_page",         "INTEGER"),
    ("  ",  "sort_order",       "INTEGER"),
    ("  ",  "created_at",       "TIMESTAMPTZ")
]
t_topics = draw_table(ax, 54, 93, 21, "TOPICS", f_topics)

# 4. TOPIC_PREREQUISITES (Self-referencing adjacency table)
f_prereqs = [
    ("PFK", "topic_id",        "INTEGER REFERENCES"),
    ("PFK", "prereq_topic_id", "INTEGER REFERENCES"),
    ("  ",  "importance_weight","SMALLINT (1-5)"),
    ("  ",  "basis",            "TEXT ('curated'/'book')")
]
t_prereqs = draw_table(ax, 79, 93, 19, "TOPIC_PREREQUISITES", f_prereqs)

# 5. STUDENT_TOPIC_COMPLETIONS
f_completions = [
    ("PK",  "completion_id", "INTEGER IDENTITY"),
    ("FK",  "user_id",       "INTEGER REFERENCES"),
    ("FK",  "topic_id",      "INTEGER REFERENCES"),
    ("  ",  "completed_at",  "TIMESTAMPTZ")
]
t_completions = draw_table(ax, 54, 60, 21, "STUDENT_TOPIC_COMPLETIONS", f_completions)

# 6. LEARNING_SESSIONS
f_sessions = [
    ("PK",  "session_id",       "UUID PRIMARY KEY"),
    ("FK",  "user_id",          "INTEGER REFERENCES"),
    ("FK",  "subject_id",       "INTEGER REFERENCES"),
    ("FK",  "current_topic_id", "INTEGER REFERENCES"),
    ("  ",  "current_stage",    "TEXT ('topic'..'clarify')"),
    ("  ",  "quiz_difficulty",  "SMALLINT (1-3)"),
    ("  ",  "confused_count",   "INTEGER >= 0"),
    ("  ",  "started_at",       "TIMESTAMPTZ"),
    ("  ",  "updated_at",       "TIMESTAMPTZ")
]
t_sessions = draw_table(ax, 14, 58, 23, "LEARNING_SESSIONS", f_sessions)

# 7. CONVERSATION_LOGS
f_logs = [
    ("PK",  "log_id",     "INTEGER IDENTITY"),
    ("FK",  "session_id", "UUID REFERENCES"),
    ("FK",  "topic_id",   "INTEGER REFERENCES"),
    ("  ",  "role",       "TEXT ('user'/'assistant')"),
    ("  ",  "stage",      "TEXT"),
    ("  ",  "content",    "TEXT"),
    ("  ",  "created_at", "TIMESTAMPTZ")
]
t_logs = draw_table(ax, 46, 26, 22, "CONVERSATION_LOGS", f_logs)

# 8. VECTOR_OPERATION_COMMITS
f_vector = [
    ("PK", "operation_id", "UUID PRIMARY KEY"),
    ("  ", "committed_at", "TIMESTAMPTZ")
]
t_vector = draw_table(ax, 79, 45, 19, "VECTOR_COMMITS", f_vector)

# ==============================================================================
# FOREIGN KEY CONNECTOR ARROWS (FK -> PK)
# ==============================================================================

# 1. SUBJECTS.created_by -> USERS.user_id
draw_fk_arrow((t_subjects["x"], t_subjects["fields"]["created_by"][1]),
              (t_users["x"] + t_users["width"], t_users["fields"]["user_id"][1]),
              "arc3,rad=-0.1")

# 2. TOPICS.subject_id -> SUBJECTS.subject_id
draw_fk_arrow((t_topics["x"], t_topics["fields"]["subject_id"][1]),
              (t_subjects["x"] + t_subjects["width"], t_subjects["fields"]["subject_id"][1]),
              "arc3,rad=0.0")

# 3. TOPIC_PREREQUISITES.topic_id -> TOPICS.topic_id
draw_fk_arrow((t_prereqs["x"], t_prereqs["fields"]["topic_id"][1]),
              (t_topics["x"] + t_topics["width"], t_topics["fields"]["topic_id"][1]),
              "arc3,rad=0.15")

# 4. TOPIC_PREREQUISITES.prereq_topic_id -> TOPICS.topic_id
draw_fk_arrow((t_prereqs["x"], t_prereqs["fields"]["prereq_topic_id"][1]),
              (t_topics["x"] + t_topics["width"], t_topics["fields"]["topic_id"][1] - 1.5),
              "arc3,rad=0.25")

# 5. COMPLETIONS.user_id -> USERS.user_id
draw_fk_arrow((t_completions["x"], t_completions["fields"]["user_id"][1]),
              (t_users["x"] + t_users["width"], t_users["fields"]["user_id"][1] - 4),
              "arc3,rad=0.2")

# 6. COMPLETIONS.topic_id -> TOPICS.topic_id
draw_fk_arrow((t_completions["x"] + t_completions["width"]/2, t_completions["y"]),
              (t_topics["x"] + t_topics["width"]/2, t_topics["y"] - t_topics["total_height"]),
              "arc3,rad=0.0")

# 7. SESSIONS.user_id -> USERS.user_id
draw_fk_arrow((t_sessions["x"], t_sessions["fields"]["user_id"][1]),
              (t_users["x"] + 10, t_users["y"] - t_users["total_height"]),
              "arc3,rad=0.15")

# 8. SESSIONS.subject_id -> SUBJECTS.subject_id
draw_fk_arrow((t_sessions["x"] + 12, t_sessions["y"]),
              (t_subjects["x"] + 10, t_subjects["y"] - t_subjects["total_height"]),
              "arc3,rad=0.0")

# 9. LOGS.session_id -> SESSIONS.session_id
draw_fk_arrow((t_logs["x"], t_logs["fields"]["session_id"][1]),
              (t_sessions["x"] + t_sessions["width"], t_sessions["fields"]["session_id"][1] - 5),
              "arc3,rad=-0.15")

# 10. LOGS.topic_id -> TOPICS.topic_id
draw_fk_arrow((t_logs["x"] + t_logs["width"], t_logs["fields"]["topic_id"][1]),
              (t_topics["x"] + 10, t_topics["y"] - t_topics["total_height"]),
              "arc3,rad=0.3")

# Title and Legend Banner
ax.text(50, 98.2, "CHAPTER1 — PHYSICAL RELATIONAL SCHEMA DIAGRAM (3NF)",
        ha="center", va="center", color="#0f172a", fontsize=15, fontweight="bold")
ax.text(50, 96.2, "Normalized Third Normal Form (3NF) Relational Mapping | PostgreSQL 18 Engine",
        ha="center", va="center", color="#475569", fontsize=10)

leg_box = patches.FancyBboxPatch(
    (4, 3), 92, 4.5, boxstyle="round,pad=0.2",
    fc="#f8fafc", ec="#cbd5e1", lw=1.2
)
ax.add_patch(leg_box)
ax.text(6, 5.25, "LEGEND:", fontweight="bold", color="#1e293b", fontsize=8.5, va="center")
ax.text(14, 5.25, "PK: Primary Key", color=PK_COLOR, fontweight="bold", fontsize=8, va="center")
ax.text(28, 5.25, "FK: Foreign Key", color=FK_COLOR, fontweight="bold", fontsize=8, va="center")
ax.text(42, 5.25, "PFK: Composite PK & FK", color=PFK_COLOR, fontweight="bold", fontsize=8, va="center")
ax.text(62, 5.25, "--> Directional Reference: points from FK to referenced PK", color=ARROW_COLOR, fontweight="bold", fontsize=8, va="center")

plt.tight_layout()
plt.savefig("docs/relational_schema_diagram.png", bbox_inches="tight", dpi=300)
print("Saved docs/relational_schema_diagram.png successfully!")
