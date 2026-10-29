"""Static game data for THE ANULMENT. All names / sign texts are original and fictional."""
TITLE_JP = "ファイアアウト・シャイン"
TITLE_EN = "THE ANULMENT"
DISTRICT_JP = "新光区・ネオン街"
DISTRICT_EN = "VALDORA - CAPITAL CITY"

# made-up shop / signboard texts (fictional, no real businesses)
SIGNS_H = ["光速ラーメン", "夜桜ホテル", "電脳カフェ", "星屑劇場", "東雲ゲーム", "炎上カラオケ", "月光薬局", "未来書店",
           "流星寿司", "銀河電機", "夢幻ビル", "紅蓮焼肉", "ネオン酒場", "深夜食堂 灯", "雷鳴ボウル", "蒼天ジム",
           "SHINE 24", "ミラージュ", "極光スパ", "夜猫バー", "宇宙うどん", "天空ラウンジ", "虹色写真館", "波動ゲームセンター",
           "鋼鉄ガレージ", "閃光タクシー", "幻影シアター", "火花ダイナー", "夜明け珈琲", "迷宮モール", "狐火 居酒屋", "HYPER NIGHT"]
SIGNS_V = ["光速ラーメン", "夜桜", "電脳", "星屑", "東雲", "炎上", "月光", "流星",
           "銀河", "夢幻", "紅蓮", "灯", "雷鳴", "蒼天", "極光", "夜猫",
           "天空", "虹色", "波動", "鋼鉄", "閃光", "幻影", "火花", "夜明け",
           "迷宮", "狐火", "新光", "疾風", "黒曜", "白夜", "朱雀", "青龍"]
NEON = [(1.0, 0.18, 0.55), (0.15, 0.85, 1.0), (1.0, 0.55, 0.1), (0.75, 0.25, 1.0), (0.2, 1.0, 0.45),
        (1.0, 0.9, 0.2), (1.0, 0.2, 0.2), (0.3, 0.45, 1.0)]

# UI strings that use Japanese glyphs (used to subset the JP font)
UI_JP = [TITLE_JP, DISTRICT_JP, "ストリートレース", "ポリスチェイス", "フリーラン", "ガレージ", "設定", "終了", "一時停止",
         "逮捕", "逃走成功", "優勝", "スタート", "チェックポイント", "手配度", "東京", "新光タワー", "首都高", "交差点",
         "主人公", "アナ", "影狼", "夜明", "残り時間", "順位", "地図", "メニュー", "再開", "やり直す", "タイトルへ"]

HEROINE = "ANA"
HEROINE_JP = "アナ"

CARS = {
    "player": {"name": "KAGEROU GT-S", "jp": "陽炎 GT-S", "body": (0.06, 0.06, 0.08), "accent": (1.0, 0.18, 0.55)},
    "rival1": {"name": "RAIJIN R9", "jp": "雷神 R9", "body": (0.9, 0.85, 0.15), "accent": (0.15, 0.85, 1.0)},
    "rival2": {"name": "KITSUNE VX", "jp": "狐 VX", "body": (0.85, 0.25, 0.05), "accent": (1.0, 0.9, 0.2)},
    "rival3": {"name": "AOI SPECTRE", "jp": "葵 スペクター", "body": (0.10, 0.25, 0.85), "accent": (0.75, 0.25, 1.0)},
}
PAINTS = [("MIDNIGHT", (0.05, 0.05, 0.07)), ("SAKURA", (0.95, 0.35, 0.62)), ("CYBER TEAL", (0.05, 0.65, 0.70)),
          ("CRIMSON", (0.75, 0.04, 0.08)), ("PEARL", (0.88, 0.88, 0.92)), ("VOLT", (0.75, 0.95, 0.10)),
          ("ULTRAVIOLET", (0.40, 0.12, 0.85)), ("SUNSET", (1.0, 0.45, 0.08))]

# ---------------- world layout
N_BLOCKS = 8; PITCH = 100.0; ROAD_W = 22.0; SIDEWALK = 4.0
CITY_MIN = -400.0; CITY_MAX = 400.0
STADIUM = (505.5, 166.5, 601.5, 298.5)       # v1.0.5 SHINE SFC 27 STADIUM footprint (Hikari Beach)
STADIUM_GATE = (503.0, 232.5)
BEACH_ROAD_X = 460.0; BEACH_ROAD_W = 16.0; BOARDWALK = (470.0, 478.0); SAND = (478.0, 602.0); SEA_X = 602.0
WORLD = (-440.0, -440.0, 690.0, 440.0)      # xmin, ymin, xmax, ymax (drivable bounds)
DISTRICTS = [  # id, name, jp, tint (minimap), popup colour
    ("crossing", "VALDORA CROSSING", "新光交差点", (0.95, 0.25, 0.60)),
    ("akari", "AKARI-CHO", "灯町", (1.00, 0.62, 0.15)),
    ("kurogane", "KUROGANE DOCKS", "黒鉄埠頭", (0.35, 0.55, 0.95)),
    ("tower", "TOWER HILL", "タワーヒル", (0.75, 0.30, 1.00)),
    ("sakura", "SAKURADAI", "桜台", (1.00, 0.45, 0.70)),
    ("beach", "HIKARI BEACH", "光ビーチ", (0.20, 0.90, 0.85)),
]
def district_at(x, y):
    if x > 411: return "beach"
    if abs(x) <= 150 and abs(y) <= 150: return "crossing"
    if x < 0: return "akari" if y >= 0 else "kurogane"
    return "tower" if y >= 0 else "sakura"
DISTRICT = {d[0]: d for d in DISTRICTS}

GARAGE_POS = (50.0, -105.5)          # FRGARAGE entrance marker (on the road in front of the garage)
GARAGE_BLOCK = (4, 2)
TOWER_BLOCK = (6, 6)
HOSPITAL_POS = (-150.0, 106.0)
HOME_POS = (436.0, -285.5)            # ANA & DANIEL'S HOUSE front door marker (Sakura side of the coast road)
HOME_CAR = (443.0, -294.5, -90.0)     # carport / driveway
HOME_INT = (-2600.0, -2600.0)         # interior set (off-map)
SPAWN = (443.0, -294.5, -90.0)        # game starts at home: x, y, heading(deg)

# race routes: lists of checkpoints (x, y)
RACES = [
    {"id": "sprint", "name": "VALDORA NIGHT SPRINT", "jp": "新光ナイトスプリント", "start": (-100.0, 0.0, -90.0), "laps": 2,
     "cps": [(100, 0), (100, 200), (-100, 200), (-100, 100), (-300, 100), (-300, -100), (-100, -100), (-100, 0)]},
    {"id": "tower", "name": "TOWER HILL CIRCUIT", "jp": "タワーヒル周回", "start": (200.0, 100.0, -90.0), "laps": 2,
     "cps": [(300, 100), (300, 300), (100, 300), (100, 400), (400, 400), (400, 100), (200, 100)]},
    {"id": "coast", "name": "HIKARI COASTAL RUN", "jp": "光ビーチ海岸ラン", "start": (300.0, -400.0, -90.0), "laps": 1,
     "cps": [(400, -400), (460, -400), (460, -100), (460, 200), (460, 400), (400, 400), (200, 400), (200, 0), (0, 0), (0, -300), (200, -300), (300, -400)]},
]
TIME_TRIAL = {"id": "tt", "name": "NEON DASH TIME TRIAL", "start": (-300.0, -200.0, 0.0), "time": 75.0,
              "cps": [(-300, 0), (-300, 300), (-100, 300), (0, 100), (0, -100), (200, -100), (200, -200), (300, -300), (400, -300), (460, -300)]}
DRIFT_ZONE = {"id": "drift", "name": "BEACH DRIFT ZONE", "rect": (480.0, -330.0, 575.0, -220.0), "start": (520.0, -275.0, 0.0), "time": 60.0}
GET_WANTED_JP = "\u6307\u540d\u624b\u914d\u3055\u308c\u308b"          # 指名手配される
GET_WANTED = "\1jp\1" + GET_WANTED_JP + "\2 GET WANTED"              # display name of the police-chase activity (JP run in Noto Sans JP)
CHASE_MISSION = {"id": "chase", "name": GET_WANTED, "start": (-300.0, 300.0, 90.0)}
DELIVERY = {"id": "delivery", "name": "NIGHT COURIER", "start": (100.0, 300.0, 0.0),
            "drops": [(-300, -300), (460, 250), (-200, 400), (300, -100), (0, -400)]}
SPEED_CAMS = [(-200.0, 50.0, "AKARI AVENUE"), (250.0, -400.0, "SAKURA BAYSIDE"), (460.0, 0.0, "COAST HIGHWAY"), (0.0, 350.0, "TOWER ROAD")]
TOKENS = [(-350, 350), (-250, 150), (-150, 380), (-380, -50), (-250, -250), (-150, -380), (-50, -150), (50, 150), (150, 50),
          (250, 380), (380, 250), (150, 250), (250, -150), (350, -350), (150, -250), (440, -380), (540, 100), (520, -100),
          (580, 300), (500, 380)]
