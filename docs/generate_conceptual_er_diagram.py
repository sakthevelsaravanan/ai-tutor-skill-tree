import matplotlib.pyplot as plt
import matplotlib.patches as patches

# ==============================================================================
# CONCEPTUAL ENTITY-RELATIONSHIP (ER) DIAGRAM GENERATOR
# Standard Chen / Crow's Foot Notation:
# - Entities: Rectangles
# - Relationships: Diamonds
# - Attributes: Ellipses / Ovals (PK underlined)
# - Cardinality: 1:N, M:N, 1:1 connectors
# ==============================================================================

fig = plt.figure(figsize=(22, 14), dpi=300)
ax = fig.add_subplot(111)
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")

# Color Palette
ENTITY_FILL = "#1e293b"       # Dark Slate (Entities)
REL_FILL = "#ea580c"          # Vivid Orange (Relationships)
ATTR_FILL = "#f8fafc"         # Off-white (Attributes)
PK_ATTR_FILL = "#fef3c7"      # Soft Amber (Key Attributes)
BORDER_DARK = "#0f172a"
LINE_COLOR = "#475569"

def draw_entity(x, y, w, h, text):
    """Draws a strong entity rectangle."""
    box = patches.FancyBboxPatch(
        (x - w/2, y - h/2), w, h,
        boxstyle="round,pad=0.1,rounding_size=0.6",
        facecolor=ENTITY_FILL, edgecolor=BORDER_DARK, linewidth=1.8, zorder=3
    )
    ax.add_patch(box)
    ax.text(x, y, text, ha="center", va="center", color="white",
            fontsize=10.5, fontweight="bold", zorder=4)

def draw_relationship(x, y, size, text):
    """Draws a relationship diamond."""
    diamond = patches.RegularPolygon(
        (x, y), numVertices=4, radius=size, orientation=0,
        facecolor=REL_FILL, edgecolor="#c2410c", linewidth=1.6, zorder=3
    )
    ax.add_patch(diamond)
    ax.text(x, y, text, ha="center", va="center", color="white",
            fontsize=8.5, fontweight="bold", zorder=4)

def draw_attribute(x, y, rx, ry, text, is_pk=False):
    """Draws an attribute ellipse."""
    ellipse = patches.Ellipse(
        (x, y), rx*2, ry*2,
        facecolor=PK_ATTR_FILL if is_pk else ATTR_FILL,
        edgecolor="#b45309" if is_pk else "#94a3b8",
        linewidth=1.4 if is_pk else 1.0, zorder=3
    )
    ax.add_patch(ellipse)
    ax.text(x, y, text, ha="center", va="center",
            color="#92400e" if is_pk else "#1e293b",
            fontsize=7.5, fontweight="bold" if is_pk else "normal", zorder=4)

def connect(p1, p2, label="", label_pos=0.5, style="-"):
    """Draws a line between two elements with optional cardinality."""
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=LINE_COLOR,
            linewidth=1.3, linestyle=style, zorder=2)
    if label:
        lx = p1[0] + (p2[0] - p1[0]) * label_pos
        ly = p1[1] + (p2[1] - p1[1]) * label_pos
        ax.text(lx, ly, label, fontsize=8.5, fontweight="bold",
                color="#b45309", ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85), zorder=5)

# ------------------------------------------------------------------------------
# 1. ENTITY COORDINATES
# ------------------------------------------------------------------------------
E_USERS = (16, 76)
E_SUBJECTS = (50, 76)
E_TOPICS = (84, 76)
E_SESSIONS = (24, 34)
E_COMPLETIONS = (50, 34)
E_LOGS = (82, 34)

# Draw Entities
draw_entity(E_USERS[0], E_USERS[1], 15, 6.5, "USERS")
draw_entity(E_SUBJECTS[0], E_SUBJECTS[1], 15, 6.5, "SUBJECTS")
draw_entity(E_TOPICS[0], E_TOPICS[1], 15, 6.5, "TOPICS")
draw_entity(E_SESSIONS[0], E_SESSIONS[1], 17, 6.5, "LEARNING_SESSIONS")
draw_entity(E_COMPLETIONS[0], E_COMPLETIONS[1], 20, 6.5, "STUDENT_TOPIC_COMPLETIONS")
draw_entity(E_LOGS[0], E_LOGS[1], 17, 6.5, "CONVERSATION_LOGS")

# ------------------------------------------------------------------------------
# 2. ATTRIBUTES
# ------------------------------------------------------------------------------
# USERS Attributes
draw_attribute(7, 89, 4.2, 1.8, "user_id", is_pk=True)
draw_attribute(16, 91, 4.2, 1.8, "email")
draw_attribute(25, 89, 4.2, 1.8, "full_name")
draw_attribute(7, 66, 4.2, 1.8, "role")
draw_attribute(16, 64, 4.2, 1.8, "password_hash")
connect((7, 87.2), (13, 79.2))
connect((16, 89.2), (16, 79.2))
connect((25, 87.2), (19, 79.2))
connect((7, 67.8), (13, 72.8))
connect((16, 65.8), (16, 72.8))

# SUBJECTS Attributes
draw_attribute(41, 90, 4.2, 1.8, "subject_id", is_pk=True)
draw_attribute(50, 92, 4.2, 1.8, "subject_key")
draw_attribute(59, 90, 4.2, 1.8, "subject_name")
draw_attribute(50, 64, 4.2, 1.8, "is_indexed")
connect((41, 88.2), (47, 79.2))
connect((50, 90.2), (50, 79.2))
connect((59, 88.2), (53, 79.2))
connect((50, 65.8), (50, 72.8))

# TOPICS Attributes
draw_attribute(75, 90, 4.2, 1.8, "topic_id", is_pk=True)
draw_attribute(84, 92, 4.2, 1.8, "topic_name")
draw_attribute(93, 90, 4.2, 1.8, "difficulty_level")
draw_attribute(93, 76, 4.0, 1.8, "sort_order")
draw_attribute(93, 66, 4.2, 1.8, "start/end_page")
connect((75, 88.2), (81, 79.2))
connect((84, 90.2), (84, 79.2))
connect((93, 88.2), (87, 79.2))
connect((89, 76), (91.5, 76))
connect((87, 72.8), (91, 67.5))

# SESSIONS Attributes
draw_attribute(12, 43, 4.6, 1.8, "session_id", is_pk=True)
draw_attribute(12, 25, 4.6, 1.8, "current_stage")
draw_attribute(24, 21, 4.6, 1.8, "confused_count")
connect((12, 41.2), (18, 37.2))
connect((12, 26.8), (18, 30.8))
connect((24, 22.8), (24, 30.8))

# COMPLETIONS Attributes
draw_attribute(40, 21, 4.6, 1.8, "completion_id", is_pk=True)
draw_attribute(60, 21, 4.6, 1.8, "completed_at")
connect((40, 22.8), (46, 30.8))
connect((60, 22.8), (54, 30.8))

# LOGS Attributes
draw_attribute(92, 43, 4.2, 1.8, "log_id", is_pk=True)
draw_attribute(93, 34, 4.2, 1.8, "role")
draw_attribute(92, 25, 4.2, 1.8, "content")
connect((89.5, 41.5), (86, 37.2))
connect((89, 34), (91, 34))
connect((89.5, 26.5), (86, 30.8))

# ------------------------------------------------------------------------------
# 3. RELATIONSHIPS & CONNECTORS
# ------------------------------------------------------------------------------
# R1: USERS --(Curates)--> SUBJECTS (1:N)
draw_relationship(33, 76, 3.8, "Curates")
connect((23.5, 76), (29.2, 76), "1", 0.4)
connect((36.8, 76), (42.5, 76), "N", 0.6)

# R2: SUBJECTS --(Contains)--> TOPICS (1:N)
draw_relationship(67, 76, 3.8, "Contains")
connect((57.5, 76), (63.2, 76), "1", 0.4)
connect((70.8, 76), (76.5, 76), "N", 0.6)

# R3: TOPICS --(Prerequisite_Of)--> TOPICS (Recursive M:N)
draw_relationship(84, 56, 4.0, "Prereq_Of")
connect((81.5, 72.8), (81.5, 60), "M", 0.4)
connect((86.5, 60), (86.5, 72.8), "N", 0.6)
# Attribute on recursive edge
draw_attribute(95, 56, 3.8, 1.7, "weight")
connect((88, 56), (91.2, 56))

# R4: USERS --(Initiates)--> LEARNING_SESSIONS (1:N)
draw_relationship(20, 54, 3.8, "Initiates")
connect((18, 72.8), (19.2, 57.8), "1", 0.3)
connect((20.8, 50.2), (22.5, 37.2), "N", 0.7)

# R5: USERS --(Completes)--> STUDENT_TOPIC_COMPLETIONS (1:N)
# TOPICS --(Completed_In)--> STUDENT_TOPIC_COMPLETIONS (1:N)
draw_relationship(38, 48, 3.8, "Completes")
connect((21, 72.8), (35, 50.5), "1", 0.3)
connect((40.5, 45.5), (46, 37.2), "N", 0.7)

draw_relationship(66, 48, 3.8, "Achieved")
connect((80, 72.8), (68.5, 50.5), "1", 0.3)
connect((63.5, 45.5), (55, 37.2), "N", 0.7)

# R6: LEARNING_SESSIONS --(Logs)--> CONVERSATION_LOGS (1:N)
draw_relationship(53, 34, 3.8, "Generates")
# Connect SESSIONS to LOGS through bottom routing
ax.plot([32.5, 49.2], [34, 34], color=LINE_COLOR, lw=1.3)
ax.plot([56.8, 73.5], [34, 34], color=LINE_COLOR, lw=1.3)
ax.text(35, 35.5, "1", color="#b45309", fontweight="bold", fontsize=8.5)
ax.text(71, 35.5, "N", color="#b45309", fontweight="bold", fontsize=8.5)

# Header & Legend
ax.text(50, 98.2, "CHAPTER1 — CONCEPTUAL ENTITY-RELATIONSHIP (ER) DIAGRAM",
        ha="center", va="center", color="#0f172a", fontsize=15, fontweight="bold")
ax.text(50, 96.2, "Chen / Crow's Foot Hybrid Notation | Normalized 3NF Conceptual Schema",
        ha="center", va="center", color="#475569", fontsize=10)

leg = patches.FancyBboxPatch((15, 3), 70, 4.5, boxstyle="round,pad=0.2",
                            fc="#f8fafc", ec="#cbd5e1", lw=1.2)
ax.add_patch(leg)
ax.text(17, 5.25, "LEGEND:", fontweight="bold", color="#1e293b", fontsize=8.5, va="center")
ax.text(26, 5.25, "Rectangle: Strong Entity", color=ENTITY_FILL, fontweight="bold", fontsize=8, va="center")
ax.text(44, 5.25, "Diamond: Relationship", color=REL_FILL, fontweight="bold", fontsize=8, va="center")
ax.text(60, 5.25, "Oval: Attribute (Yellow = Primary Key)", color="#92400e", fontweight="bold", fontsize=8, va="center")

plt.tight_layout()
plt.savefig("docs/conceptual_er_diagram.png", bbox_inches="tight", dpi=300)
print("Saved docs/conceptual_er_diagram.png successfully!")
