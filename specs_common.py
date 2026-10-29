# shared PyInstaller config for THE ANULMENT
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files
import os, glob
DROP = ('avcodec', 'avformat', 'avutil', 'swresample', 'swscale', 'libp3ffmpeg', 'fmod', 'assimp', 'ptloader',
        'bullet', 'pandaode', 'pandaai', 'vrpn', 'p3vision', 'pandadx9', 'd3dx9', 'cgd3d9', 'pandaphysics', 'pandafx')
BINS = [x for x in collect_dynamic_libs('panda3d') if not any(k in os.path.basename(x[0]).lower() for k in DROP)]
DATAS = collect_data_files('panda3d', includes=['etc/*'])
ASSETS = [(f, 'assets') for f in ('assets/start.jpg', 'assets/icon.ico', 'assets/icon.png', 'assets/ui_font.ttf', 'assets/ui_plain.ttf',
                                  'assets/sym_font.ttf', 'assets/THIRD_PARTY.txt')]
ASSETS += [('assets/sfx', 'assets/sfx'), ('assets/music', 'assets/music'), ('assets/voice', 'assets/voice'), ('assets/tex', 'assets/tex')]
ASSETS += [(f, 'assets/models') for f in glob.glob('assets/models/*.bam') + glob.glob('assets/models/*.json') + glob.glob('assets/models/cover_*.npz')]
ASSETS += [('piper_win', 'piper')]      # Piper TTS (MIT) Windows binaries + espeak-ng-data
HIDDEN = ['panda3d.core', 'panda3d.direct', 'direct.showbase.ShowBase', 'direct.gui.DirectGui', 'an_game', 'an_base', 'an_people', 'an_hair', 'an_cover', 'an_crowd', 'an_tts',
          'fs_world', 'fs_geom', 'fs_vehicle', 'fs_people', 'fs_ai', 'fs_ui', 'fs_data', 'fs_shaders', 'fs_miyo', 'fs_signals', 'numpy']
EXCL = ['matplotlib', 'scipy', 'pandas', 'IPython', 'pytest', 'tkinter', 'PIL', 'cv2', 'wx', 'PyQt5', 'imageio_ffmpeg', 'onnxruntime']
