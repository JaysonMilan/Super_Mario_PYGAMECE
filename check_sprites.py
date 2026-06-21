import json
import re
import os

# Load all atlas sprite names
data = json.load(open('assets/processed/atlases/atlases.json'))
atlas_sprites = {}
for atlas_name, atlas in data['atlases'].items():
    for name in atlas['sprites']:
        atlas_sprites[name] = atlas_name

# SPRITE_ALIASES from assets.py
aliases = {
    'coin': 'coin_0',
    'goomba': 'goombas_0',
    'small_mario': 'mario_st',
    'small_mario_stand': 'mario_st',
    'small_mario_jump': 'mario_jump',
    'small_mario_walk0': 'mario_move0',
    'small_mario_walk1': 'mario_move1',
    'small_mario_walk2': 'mario_move2',
    'question_block': 'blockq_0',
    'used_block': 'blockq_used',
    'ground': 'gnd_red_1',
    'flag': 'end0_flag',
}

def resolve(name):
    if name in atlas_sprites:
        return name
    a = aliases.get(name)
    if a and a in atlas_sprites:
        return a
    return None

# Read all Python source files
src_dir = 'python_src/super_mario_pygamece'
all_text = ''
for fn in sorted(os.listdir(src_dir)):
    if fn.endswith('.py'):
        content = open(os.path.join(src_dir, fn)).read()
        all_text += content + '\n'

# Extract all string literals from source
all_literals = re.findall(r'"([\w_]+)"', all_text)
all_literals += re.findall(r"'([\w_]+)'", all_text)

# Deduplicate
found_names = sorted(set(all_literals))

print('=== SPRITE NAMES IN CODE MISSING FROM ATLAS ===')
SKIP_WORDS = {
    'png','json','mp3','wav','ogg','utf','left','right','none','true','false',
    'walk','idle','jump','squat','death','lvlup','underwater','running',
    'mario','luigi','hammer','fire','fireball','bowser','goombas','koopa',
    'lakito','spikey','cheep','squid','beetle','plant','hammerbro','lava',
    'bullet','b_top','blockq','brick','gnd','castle','end','vine','spring',
    'coin','mushroom','star','flower','goombas','similalrly','int','str',
    'in_progress','pending','completed',
}

missing = []
for name in found_names:
    if len(name) < 4:
        continue
    if any(name == s or name.startswith(s+'_') for s in SKIP_WORDS):
        continue
    resolved = resolve(name)
    if resolved is None:
        missing.append(name)

for m in sorted(set(missing)):
    print(f'  MISSING: {m}')

print()
print('=== ALL CONFIRMED SPRITE NAMES IN ATLAS ===')
found_in_atlas = {}
for name in found_names:
    r = resolve(name)
    if r and len(name) >= 4:
        found_in_atlas[name] = atlas_sprites[r]

# Group by atlas
by_atlas = {}
for name, atlas in found_in_atlas.items():
    by_atlas.setdefault(atlas, []).append(name)

for atlas_name in sorted(by_atlas):
    print(f'\n  [{atlas_name}]')
    for n in sorted(by_atlas[atlas_name]):
        print(f'    {n}')
