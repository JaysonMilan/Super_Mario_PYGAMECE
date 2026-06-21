import json

data = json.load(open('assets/processed/atlases/atlases.json'))
atlas_sprites = {}
for atlas_name, atlas in data['atlases'].items():
    for name in atlas['sprites']:
        atlas_sprites[name] = atlas_name

def check(name):
    status = "OK" if name in atlas_sprites else "MISSING"
    atlas = atlas_sprites.get(name, "---")
    print(f"  [{status}] {name}  ({atlas})")

# All dynamically-generated sprite names used in the Python code
print("=== PLAYER SPRITES ===")
for prefix in ["mario", "mario1", "mario2"]:
    for suffix in ["", "_st", "_jump", "_squat", "_move0", "_move1", "_move2",
                   "_underwater0", "_underwater1", "_death", "_lvlup",
                   "_end", "_end1"]:
        check(prefix + suffix)
    print()

print("=== COIN ANIMATION ===")
for i in range(4):
    check(f"coin_an{i}")
check("coin_0")
check("coin_1")
check("coin_2")

print("\n=== FIREBALL / FIRE ===")
for i in range(4):
    check(f"fireball_{i}")
for i in range(2):
    check(f"fire_{i}")
check("upfire")

print("\n=== STAR ===")
for i in range(4):
    check(f"star_{i}")

print("\n=== FLOWER ===")
for i in range(4):
    check(f"flower{i}")

print("\n=== HAMMER ===")
for i in range(4):
    check(f"hammer_{i}")

print("\n=== QUESTION BLOCK ===")
for i in range(3):
    check(f"blockq_{i}")
check("blockq_used")

print("\n=== ENEMY WALK FRAMES ===")
for name in [
    "goombas_0","goombas_1","goombas_ded",
    "koopa_0","koopa_1","koopa_ded",
    "koopa2_0","koopa2_1","koopa2_ded",
    "koopa1_2","koopa1_3","koopa1_ded",
    "beetle_0","beetle_1","beetle_2",
    "spikey0_0","spikey0_1",
    "spikey1_0","spikey1_1",
    "plant_0","plant_1",
    "hammerbro_0","hammerbro_1",
    "hammerbro_2","hammerbro_3",
    "bowser0","bowser1","bowser2","bowser3",
    "lakito_0","lakito_1",
    "bulletbill",
    "b_top","b_top1",
    "cheep0","cheep1",
    "squid0","squid1",
    "lava_0","lava_1",
]:
    check(name)

print("\n=== GOAL POLE ===")
for name in ["end0_l","end0_dot","end0_flag","castle0_top0","axe_0","axe_1","axe_2"]:
    check(name)

print("\n=== TILES ===")
for name in [
    "gnd_red_1","brick1","brickred",
    "platform",
    "pipe_left_top","pipe_right_top","pipe_left_bot","pipe_right_bot",
    "vine","vine_top","vine1","vine1_top",
    "spring_0","spring_1","spring_2",
    "castle_flag",
    "firework0","firework1","firework2",
]:
    check(name)

print("\n=== COLLECTIBLES ===")
for name in ["mushroom","mushroom_1up","mushroom1_1up"]:
    check(name)

print("\n=== EFFECTS ===")
for name in ["koopa_shell_feet_0","koopa_shell_feet_1","toad","super_mario_bros"]:
    check(name)
