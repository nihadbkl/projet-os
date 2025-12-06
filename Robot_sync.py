import threading
import random
import time
import tkinter as tk
from queue import Queue, Empty
import heapq
import math

# ----------------------------
# إعدادات الخريطة والروبوتات
# ----------------------------
ROWS = 12
COLS = 16
CELL_SIZE = 40
NUM_ROBOTS = 5
MAX_ROBOTS = 12

# الشبكة وحالة الخلايا (0 = فارغ, >0 = robot id)
grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]
# (لا نستخدم قفل خلية فردي هنا لأن الحركة تمر عبر MovementManager)
robot_colors = ["red","blue","green","orange","purple","cyan","magenta","yellow","pink","brown","gray","lime"]

# ----------------------------
# واجهة المستخدم وآلية التحديث من الخيوط
# ----------------------------
root = tk.Tk()
root.title("Ultimate Smart Robot Simulation — Final")

# نجعل الـ canvas أصغر من الشبكة لتفعيل ال-scroll (مربع عرضي)
CANVAS_VIEW_W = min(800, COLS * CELL_SIZE)
CANVAS_VIEW_H = min(600, ROWS * CELL_SIZE)

canvas_frame = tk.Frame(root)
canvas_frame.grid(row=0, column=0, columnspan=6)

h_scroll = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
v_scroll = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
canvas = tk.Canvas(canvas_frame, width=CANVAS_VIEW_W, height=CANVAS_VIEW_H,
                   xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
h_scroll.config(command=canvas.xview)
v_scroll.config(command=canvas.yview)
h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
canvas.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

# set scrollregion to full grid
canvas.config(scrollregion=(0,0,COLS*CELL_SIZE, ROWS*CELL_SIZE))

# طابور لتحديث واجهة المستخدم من الخيوط بأمان
ui_queue = Queue()

def schedule_update_cell(x, y, robot_id):
    ui_queue.put(("cell", x, y, robot_id))

def schedule_update_stats():
    ui_queue.put(("stats",))

def schedule_draw_path(rid, path):
    ui_queue.put(("path", rid, list(path)))

def schedule_clear_path(rid):
    ui_queue.put(("clear_path", rid))

def schedule_follow(rid):
    ui_queue.put(("follow", rid))

def process_ui_queue():
    try:
        while True:
            item = ui_queue.get_nowait()
            kind = item[0]
            if kind == "cell":
                _, x, y, robot_id = item
                _do_update_cell(x, y, robot_id)
            elif kind == "stats":
                _do_update_stats()
            elif kind == "path":
                _, rid, path = item
                _do_draw_path(rid, path)
            elif kind == "clear_path":
                _, rid = item
                _do_clear_path(rid)
            elif kind == "follow":
                _, rid = item
                _do_follow_center(rid)
    except Empty:
        pass
    root.after(40, process_ui_queue)

# ----------------------------
# رسم الشبكة (مخزن للأشكال)
# ----------------------------
rects = [[None for _ in range(COLS)] for _ in range(ROWS)]
texts = [[None for _ in range(COLS)] for _ in range(ROWS)]
for i in range(ROWS):
    for j in range(COLS):
        rects[i][j] = canvas.create_rectangle(
            j*CELL_SIZE, i*CELL_SIZE, (j+1)*CELL_SIZE, (i+1)*CELL_SIZE,
            fill="white", outline="black"
        )

# مسارات مرسومة لكل روبوت (IDs of canvas items)
path_items = {}  # rid -> [item,...]
follow_rect = None

def _do_update_cell(x, y, robot_id):
    global texts
    if robot_id == 0:
        canvas.itemconfig(rects[x][y], fill="white")
        if texts[x][y]:
            canvas.delete(texts[x][y])
            texts[x][y] = None
    else:
        color = robot_colors[(robot_id-1) % len(robot_colors)]
        canvas.itemconfig(rects[x][y], fill=color)
        if texts[x][y]:
            canvas.delete(texts[x][y])
        texts[x][y] = canvas.create_text(
            y*CELL_SIZE + CELL_SIZE//2,
            x*CELL_SIZE + CELL_SIZE//2,
            text=str(robot_id),
            fill="white",
            font=("Arial", 12, "bold")
        )
def _do_draw_path(rid, path):
    # مسح أي مسار سابق
    _do_clear_path(rid)
    items = []
    if not path:
        path_items[rid] = []
        return
    # تحويل كل مركز خلية إلى إحداثيات
    coords = []
    for (x,y) in path:
        cx = y*CELL_SIZE + CELL_SIZE//2
        cy = x*CELL_SIZE + CELL_SIZE//2
        coords.extend([cx, cy])
    # draw a dashed polyline
    line = canvas.create_line(*coords, dash=(4,6), width=2)
    items.append(line)
    path_items[rid] = items

def _do_clear_path(rid):
    items = path_items.get(rid, [])
    for it in items:
        try:
            canvas.delete(it)
        except Exception:
            pass
    path_items[rid] = []

def _do_update_stats():
    lines = []
    for rid, data in sorted(robot_stats.items()):
        status = "Paused" if robot_pause_flags.get(rid, False) else "Running"
        lines.append(f"R{rid}: {data['moves']}m/{data['distance']}d ({status})")
    stats_label.config(text=" | ".join(lines))

def _do_follow_center(rid):
    # center view on robot rid if present
    # find robot coords
    pos = robot_positions.get(rid)
    if not pos:
        return
    x,y = pos
    # center coordinates (canvas coords)
    cx = y*CELL_SIZE + CELL_SIZE//2
    cy = x*CELL_SIZE + CELL_SIZE//2
    total_w = COLS*CELL_SIZE
    total_h = ROWS*CELL_SIZE
    # compute fraction for xview_moveto / yview_moveto
    fx = max(0.0, min(1.0, (cx - CANVAS_VIEW_W/2) / max(1, total_w - CANVAS_VIEW_W)))
    fy = max(0.0, min(1.0, (cy - CANVAS_VIEW_H/2) / max(1, total_h - CANVAS_VIEW_H)))
    canvas.xview_moveto(fx)
    canvas.yview_moveto(fy)
    # highlight followed robot by drawing a rectangle around it
    global follow_rect
    if follow_rect:
        try:
            canvas.delete(follow_rect)
        except Exception:
            pass
    x1 = y*CELL_SIZE
    y1 = x*CELL_SIZE
    follow_rect = canvas.create_rectangle(x1+2, y1+2, x1+CELL_SIZE-2, y1+CELL_SIZE-2, outline="black", width=3)

# ----------------------------
# إحصائيات و Flags
# ----------------------------
robot_stats = {}       # rid -> {'moves','distance'}
robot_pause_flags = {} # rid -> bool
robot_positions = {}   # rid -> (x,y)
robot_threads = {}     # rid -> thread
stop_events = {}       # rid -> Event
robot_priority = {}    # rid -> integer priority (قيمة أقل => أولوية أعلى)

stats_label = tk.Label(root, text="", font=("Arial", 10))
stats_label.grid(row=1, column=0, columnspan=6, sticky="w", padx=6)

# ----------------------------
# خوارزمية A* (أفضل من BFS لمسافات طويلة)
# ----------------------------
def astar(start, goal):
    (sx, sy) = start
    (gx, gy) = goal
    def h(a,b):
        # معيار Manhattan
        return abs(a[0]-b[0]) + abs(a[1]-b[1])

    open_set = []
    heapq.heappush(open_set, (h(start, goal), 0, start, [start]))  # (f, g, node, path)
    closed = set()
    while open_set:
        f, g, node, path = heapq.heappop(open_set)
        if node == goal:
            return path[1:]  # استثناء الخانة الحالية
        if node in closed:
            continue
        closed.add(node)
        x,y = node
        for dx,dy in [(0,1),(0,-1),(1,0),(-1,0)]:
            nx, ny = x+dx, y+dy
            if 0 <= nx < ROWS and 0 <= ny < COLS:
                if (nx,ny) in closed:
                    continue
                # treat occupied cells as high cost / blocked
                occ = 1 if grid[nx][ny] != 0 else 0
                new_g = g + 1 + occ*10  # if occupied, heavy cost to avoid
                new_path = path + [(nx,ny)]
                new_f = new_g + h((nx,ny), goal)
                heapq.heappush(open_set, (new_f, new_g, (nx,ny), new_path))
    return []

# ----------------------------
# تجنّب الاصطدام الذكي (كما قبل)
# ----------------------------
def avoid_collision(x, y, path, robot_id):
    if not path:
return path
    nx, ny = path[0]
    danger = False
    for dx,dy in [(0,1),(0,-1),(1,0),(-1,0)]:
        cx, cy = nx+dx, ny+dy
        if 0 <= cx < ROWS and 0 <= cy < COLS:
            if grid[cx][cy] != 0 and grid[cx][cy] != robot_id:
                danger = True
                break
    if not danger:
        return path
    alternatives = []
    for dx,dy in [(0,1),(0,-1),(1,0),(-1,0)]:
        ax, ay = x+dx, y+dy
        if 0 <= ax < ROWS and 0 <= ay < COLS and grid[ax][ay] == 0:
            alternatives.append((ax,ay))
    if alternatives:
        return [random.choice(alternatives)] + path
    return path

# ----------------------------
# مدير الحركة المركزي (يمنح أذونات خطوة بخطوة)
# ----------------------------
class MovementManager(threading.Thread):
    def init(self):
        super().init(daemon=True)
        self.lock = threading.Lock()
        self.counter = 0  # لاحتساب زمن الطلب
        self.requests = []  # heap of (priority_key, counter, to_x,to_y, robot_id, from_x,from_y, event)
        self.running = True

    def request_move(self, robot_id, from_pos, to_pos, prio):
        # prio: lower better
        event = threading.Event()
        with self.lock:
            self.counter += 1
            key = (prio, self.counter)  # الأولوية ثم زمن الطلب
            heapq.heappush(self.requests, (key, to_pos[0], to_pos[1], robot_id, from_pos[0], from_pos[1], event))
        return event

    def run(self):
        while self.running:
            granted_any = False
            with self.lock:
                if not self.requests:
                    pass
                else:
                    # ننسخ قائمة لمعالجة بدون تغيير الـ heap أثناء التكرار
                    temp = []
                    while self.requests:
                        temp.append(heapq.heappop(self.requests))
                    # process temp in order (they are already ordered by key)
                    remaining = []
                    for req in temp:
                        key, tx, ty, rid, fx, fy, ev = req
                        # إذا الخانة المطلوبة فارغة أو مملوكة من نفس الروبوت (edge)
                        if grid[tx][ty] == 0:
                            # منح الإذن:
                            grid[tx][ty] = rid  # نضع الروبوت مؤقتاً في الخانة الجديدة
                            # نترك خانة القديمة مبدئياً لفراغها بعد إخبار الروبوت
                            ev.set()
                            granted_any = True
                        else:
                            # لا يمكن منحها الآن — نعيد الطلب مع زيادة الأولوية الزمنية (sooner retry later)
                            remaining.append(req)
                    # ضع الطلبات الباقية مجدداً في self.requests مع تحديث counter
                    for req in remaining:
                        heapq.heappush(self.requests, req)
            # بعد منح الأذونات، ننتظر قليلاً للسماح للروبوتات تنفذ الخطوة وتحرر القديم
            if not granted_any:
                time.sleep(0.02)
            else:
                time.sleep(0.01)

    def stop(self):
        self.running = False

movement_manager = MovementManager()
movement_manager.start()

# ----------------------------
# سلوك الروبوتات (كل روبوت يطلب إذن خطوة بخطوة)
# ----------------------------
speed_lock = threading.Lock()
speed = 0.18
def set_speed_ns(val):
    global speed
    with speed_lock:
        speed = max(0.02, val)
def get_speed_ns():
    with speed_lock:
        return speed

def find_empty_start():
    for attempts in range(500):
        sx, sy = random.randint(0, ROWS-1), random.randint(0, COLS-1)
        if grid[sx][sy] == 0:
            grid[sx][sy] = -999  # حجز مؤقت
            return sx, sy
    # fallback: scan
    for i in range(ROWS):
        for j in range(COLS):
            if grid[i][j] == 0:
                grid[i][j] = -999
                return i,j
    return None, None
def robot_thread(rid, stop_ev):
    # اختيار بداية
    sx, sy = find_empty_start()
    if sx is None:
        return
    grid[sx][sy] = rid
    robot_positions[rid] = (sx, sy)
    schedule_update_cell(sx, sy, rid)
    robot_stats[rid] = {'moves':0, 'distance':0}
    robot_pause_flags[rid] = False
    schedule_update_stats()

    x, y = sx, sy
    prio = robot_priority.get(rid, rid)  # افتراضي: id كأولوية

    while not stop_ev.is_set():
        # pause
        while robot_pause_flags.get(rid, False) and not stop_ev.is_set():
            time.sleep(0.1)

        # اختيار هدف ذكي
        target = None
        for _ in range(200):
            tx, ty = random.randint(0, ROWS-1), random.randint(0, COLS-1)
            if (tx,ty) != (x,y) and grid[tx][ty] == 0 and (abs(tx-x)+abs(ty-y) >= 2 or random.random() < 0.1):
                target = (tx,ty)
                break
        if not target:
            # fallback
            for i in range(ROWS):
                for j in range(COLS):
                    if grid[i][j] == 0:
                        target = (i,j)
                        break
                if target:
                    break
        if not target:
            time.sleep(0.1)
            continue

        # حساب مسار A* و تجنّب اصطدام
        path = astar((x,y), target)
        path = avoid_collision(x, y, path, rid)
        schedule_draw_path(rid, path)

        # تنفيذ المسار خطوة بخطوة عبر MovementManager
        for step in list(path):
            if stop_ev.is_set():
                break
            if robot_pause_flags.get(rid, False):
                break
            nx, ny = step
            # اطلب إذن من المدير
            ev = movement_manager.request_move(rid, (x,y), (nx,ny), prio)
            # ننتظر إذن أو timeout
            got = ev.wait(timeout=0.7)
            if not got:
                # لم يمنح الإذن خلال الوقت -> نعيد حساب المسار
                path = astar((x,y), target)
                path = avoid_collision(x, y, path, rid)
                schedule_draw_path(rid, path)
                continue
            # إذن مُعطى: المدير وضع الروبوت مؤقتاً في الخانة الجديدة (grid[nx][ny]=rid)
            # لذا نحرر الخانة القديمة فعليًا
            try:
                if grid[x][y] == rid:
                    grid[x][y] = 0
            except Exception:
                pass
            # حدّث الوضعيات والإحصائيات
            robot_positions[rid] = (nx, ny)
            schedule_update_cell(x, y, 0)
            schedule_update_cell(nx, ny, rid)
            robot_stats[rid]['moves'] += 1
            robot_stats[rid]['distance'] += 1
            schedule_update_stats()
            x,y = nx, ny
            # بعد الحركة، فاصل زمني بحسب السرعة
            time.sleep(get_speed_ns())
        schedule_clear_path(rid)
        # استمر لحلقة اختيار هدف جديد

    # إنهاء: تحرير الخانة الحالية إن بقيت مشغولة
    try:
        if robot_positions.get(rid) == (x,y) and grid[x][y] == rid:
            grid[x][y] = 0
            schedule_update_cell(x, y, 0)
    except Exception:
        pass

# ----------------------------
# إدارة الروبوتات (Start/Stop/Add/Pause/Priority)
# ----------------------------
def start_simulation():
    global robot_threads, stop_events
    if robot_threads:
        return
    robot_threads = {}
    stop_events = {}
    for i in range(1, NUM_ROBOTS+1):
        ev = threading.Event()
        stop_events[i] = ev
        # priority arbitrarily set: smaller id => higher priority (user can change)
        robot_priority[i] = i
        t = threading.Thread(target=robot_thread, args=(i, ev), daemon=True)
        robot_threads[i] = t
        t.start()

def stop_all():
    # اطلب من الجميع التوقف
    for rid, ev in list(stop_events.items()):
        ev.set()
    # clear state
    robot_threads.clear()
    stop_events.clear()
    robot_stats.clear()
    robot_pause_flags.clear()
    robot_positions.clear()
    # clear grid
    for i in range(ROWS):
        for j in range(COLS):
            grid[i][j] = 0
            schedule_update_cell(i, j, 0)
    schedule_update_stats()
def add_robot():
    global NUM_ROBOTS
    if NUM_ROBOTS < MAX_ROBOTS:
        NUM_ROBOTS += 1
        rid = NUM_ROBOTS
        ev = threading.Event()
        stop_events[rid] = ev
        robot_priority[rid] = rid
        t = threading.Thread(target=robot_thread, args=(rid, ev), daemon=True)
        robot_threads[rid] = t
        t.start()

def toggle_pause(rid):
    if rid not in robot_pause_flags:
        return
    robot_pause_flags[rid] = not robot_pause_flags[rid]
    schedule_update_stats()

def set_priority(rid, newp):
    robot_priority[rid] = newp

# ----------------------------
# واجهة المستخدم: أزرار، اختيار متابعة، تحكم سرعة، ترتيب الأولويات
# ----------------------------
start_btn = tk.Button(root, text="Start", command=start_simulation, width=12)
start_btn.grid(row=2, column=0, padx=4, pady=6)

add_btn = tk.Button(root, text="Add Robot", command=add_robot, width=12)
add_btn.grid(row=2, column=1, padx=4, pady=6)

faster_btn = tk.Button(root, text="Faster", command=lambda: set_speed_ns(max(0.02, get_speed_ns()-0.03)), width=12)
faster_btn.grid(row=2, column=2, padx=4, pady=6)

slower_btn = tk.Button(root, text="Slower", command=lambda: set_speed_ns(get_speed_ns()+0.03), width=12)
slower_btn.grid(row=2, column=3, padx=4, pady=6)

stop_btn = tk.Button(root, text="Stop/Reset", command=stop_all, width=12)
stop_btn.grid(row=2, column=4, padx=4, pady=6)

# Pause buttons
pause_frame = tk.Frame(root)
pause_frame.grid(row=3, column=0, columnspan=6, sticky="w")
tk.Label(pause_frame, text="Pause/Resume: ").pack(side=tk.LEFT)
for i in range(1, MAX_ROBOTS+1):
    robot_pause_flags[i] = False
    b = tk.Button(pause_frame, text=f"R{i}", command=lambda rid=i: toggle_pause(rid), width=3)
    b.pack(side=tk.LEFT, padx=2)

# Priority controls
prio_frame = tk.Frame(root)
prio_frame.grid(row=4, column=0, columnspan=6, sticky="w")
tk.Label(prio_frame, text="Set Priority (lower = higher): ").pack(side=tk.LEFT)
prio_entries = {}
for i in range(1, MAX_ROBOTS+1):
    e = tk.Entry(prio_frame, width=3)
    e.insert(0, str(i))
    e.pack(side=tk.LEFT, padx=1)
    prio_entries[i] = e
def apply_priorities():
    for rid, ent in prio_entries.items():
        try:
            v = int(ent.get())
            set_priority(rid, v)
        except:
            pass
apply_btn = tk.Button(prio_frame, text="Apply", command=apply_priorities)
apply_btn.pack(side=tk.LEFT, padx=6)

# Follow robot control
follow_var = tk.IntVar(value=0)
follow_frame = tk.Frame(root)
follow_frame.grid(row=5, column=0, columnspan=6, sticky="w")
tk.Label(follow_frame, text="Follow Robot: ").pack(side=tk.LEFT)
follow_spin = tk.Spinbox(follow_frame, from_=0, to=MAX_ROBOTS, textvariable=follow_var, width=5)
follow_spin.pack(side=tk.LEFT)
def follow_action():
    rid = follow_var.get()
    if rid == 0:
        # clear follow rect
        ui_queue.put(("clear_path", 0))  # just reuse to clear potential items
    else:
        schedule_follow(rid)
follow_btn = tk.Button(follow_frame, text="Center", command=follow_action)
follow_btn.pack(side=tk.LEFT, padx=6)

# stats update trigger
root.after(100, process_ui_queue)

# ----------------------------
# تشغيل التطيبق
# ----------------------------
root.mainloop()

# عند الخروج نوقف مدير الحركة
movement_manager.stop()
