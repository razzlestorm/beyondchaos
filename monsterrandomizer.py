from utils import hex2int, write_multi, read_multi
from skillrandomizer import SpellBlock
import random


stat_order = ['speed', 'attack', 'hit%', 'evade%', 'mblock%',
              'def', 'mdef', 'mpow']
all_spells = None
valid_spells = None
unrageable = [0x7E, 0x7F, 0x80, 0x81]


class MonsterBlock:
    def __init__(self, name, pointer, itemptr, controlptr, sketchptr, rageptr):
        self.name = name
        self.pointer = hex2int(pointer)
        self.itemptr = hex2int(itemptr)
        self.controlptr = hex2int(controlptr)
        self.sketchptr = hex2int(sketchptr)
        self.rageptr = hex2int(rageptr)
        self.stats = {}

    def set_id(self, i):
        self.id = i

    def read_stats(self, filename):
        global all_spells, valid_spells

        f = open(filename, 'r+b')
        f.seek(self.pointer)
        for key in stat_order:
            self.stats[key] = ord(f.read(1))
        self.stats['hp'] = read_multi(f, length=2)
        self.stats['mp'] = read_multi(f, length=2)
        self.stats['xp'] = read_multi(f, length=2)
        self.stats['gp'] = read_multi(f, length=2)
        self.stats['level'] = ord(f.read(1))

        self.morph = ord(f.read(1))
        f.seek(self.pointer + 20)
        self.immunities = map(ord, f.read(3))
        self.absorb = ord(f.read(1))
        self.null = ord(f.read(1))
        self.weakness = ord(f.read(1))

        f.seek(self.pointer + 27)
        self.statuses = map(ord, f.read(4))
        self.special = ord(f.read(1))

        f.seek(self.itemptr)
        self.items = map(ord, f.read(4))

        f.seek(self.controlptr)
        self.controls = map(ord, f.read(4))

        f.seek(self.sketchptr)
        self.sketches = map(ord, f.read(2))

        f.seek(self.rageptr)
        self.rages = map(ord, f.read(2))

        all_spells = sorted([SpellBlock(i, filename) for i in xrange(0xFF)],
                            key=lambda s: s.rank())
        valid_spells = filter(lambda sb: sb.spellid not in unrageable and
                              not sb.abort_on_allies, all_spells)

        f.close()

    def write_stats(self, filename):
        f = open(filename, 'r+b')
        f.seek(self.pointer)
        for key in stat_order:
            f.write(chr(self.stats[key]))
        write_multi(f, self.stats['hp'], length=2)
        write_multi(f, self.stats['mp'], length=2)
        write_multi(f, self.stats['xp'], length=2)
        write_multi(f, self.stats['gp'], length=2)
        f.write(chr(self.stats['level']))

        f.write(chr(self.morph))
        f.seek(self.pointer + 20)
        for i in self.immunities:
            f.write(chr(i))
        f.write(chr(self.absorb))
        f.write(chr(self.null))
        f.write(chr(self.weakness))

        f.seek(self.pointer + 27)
        for s in self.statuses:
            f.write(chr(s))
        f.write(chr(self.special))

        f.seek(self.itemptr)
        f.write(''.join(map(chr, self.items)))

        f.seek(self.controlptr)
        f.write(''.join(map(chr, self.controls)))

        f.seek(self.sketchptr)
        f.write(''.join(map(chr, self.sketches)))

        f.seek(self.rageptr)
        f.write(''.join(map(chr, self.rages)))

        f.close()

    def screw_vargas(self):
        if 'vargas' in self.name.lower():
            self.stats['hp'] = 1000 + random.randint(0, 400) + random.randint(0, 400)

    def mutate_stats(self):
        level = self.stats['level']

        def level_boost(value, limit=0xFE):
            low = value
            high = int(value + (value * (level / 100.0)))
            diff = high - low
            value = value + random.randint(0, diff) + random.randint(0, diff)
            if value & 0xFF == 0xFF:
                value = value - 1

            return min(value, limit)

        for stat in ['speed', 'attack', 'hit%', 'evade%', 'mblock%',
                     'def', 'mdef', 'mpow']:
            self.stats[stat] = level_boost(self.stats[stat])

        self.stats['hp'] = level_boost(self.stats['hp'], limit=0xFEFE)
        self.stats['mp'] = level_boost(self.stats['mp'], limit=0xFEFE)

        def fuddle(value, limit=0xFEFE):
            low = value / 2
            value = low + random.randint(0, low) + random.randint(0, low)
            if value & 0xFF == 0xFF:
                value = value - 1

            return min(value, limit)

        self.stats['xp'] = fuddle(self.stats['xp'])
        self.stats['gp'] = fuddle(self.stats['gp'])

        if random.randint(1, 10) == 10:
            level += random.choice([1, -1])
            if random.randint(1, 5) == 5:
                level += random.choice([1, -1])
        level = min(level, 99)
        level = max(level, 0)
        self.stats['level'] = level

    def mutate_statuses(self):
        new_immunities = [0x00] * 3
        new_statuses = [0x00] * 4
        immcount = sum([bin(v).count('1') for v in self.immunities])
        stacount = sum([bin(v).count('1') for v in self.statuses])
        stacount += 1
        while stacount > 0:
            byte = random.randint(0, 3)
            bit = 1 << random.randint(0, 7)
            if byte == 0 and bit in [0x02, 0x40, 0x80]:
                # zombie, dead, petrify
                continue

            if new_statuses[byte] & bit:
                continue

            new_statuses[byte] = new_statuses[byte] | bit
            if byte <= 2 and random.randint(1, 10) > 3:
                new_immunities[byte] = new_immunities[byte] | bit
            stacount += -1

        while immcount > 0:
            byte = random.randint(0, 2)
            bit = 1 << random.randint(0, 7)
            new_immunities[byte] = new_immunities[byte] | bit
            immcount += -1

        self.statuses = new_statuses
        self.immunities = new_immunities

    def mutate_affinities(self):
        abscount = min(bin(self.absorb).count('1') + 1, 8)
        nullcount = min(bin(self.null).count('1') + 1, 8)
        weakcount = min(bin(self.weakness).count('1'), 8)
        self.absorb, self.null, self.weakness = 0, 0, 0
        while abscount > 0:
            bit = 1 << random.randint(0, 7)
            if self.absorb & bit:
                continue

            self.absorb = self.absorb | bit
            abscount += -1

        while nullcount > 0:
            bit = 1 << random.randint(0, 7)
            if self.null & bit:
                continue
            self.null = self.null | bit
            nullcount += -1

        while weakcount > 0:
            bit = 1 << random.randint(0, 7)
            if self.weakness & bit:
                continue
            self.weakness = self.weakness | bit
            weakcount += -1

    def mutate_items(self):
        self.itemptr

    def mutate_control(self):
        # shuffle skills between control, sketch, rage
        candidates = set(self.controls + self.sketches + self.rages)
        candidates.add(0xEE)
        candidates.add(0xEF)
        if 0xFF in candidates:
            candidates.remove(0xFF)

        if random.randint(1, 10) >= 9:
            index = None
            while index is None or index in unrageable:
                median = len(valid_spells) / 2
                index = random.randint(0, median) + random.randint(0, median)
                if len(valid_spells) % 2:
                    index += random.randint(0, 1)
                sb = valid_spells[index]
            candidates.add(sb.spellid)

        candidates = list(candidates)
        self.controls = sorted(random.sample(candidates,
                                             min(4, len(candidates))))
        self.sketches = random.sample(candidates, 2)
        self.rages = random.sample(candidates, 2)
        while len(self.controls) < 4:
            self.controls.append(0xFF)

    def mutate_special(self):
        branch = random.randint(1, 10)
        if branch <= 7:
            # regular special
            valid = set(range(0, 0x0F))
            valid.remove(0x03)
            valid.remove(0x0A)
            valid.add(0x19)
            valid.add(0x30)
            valid.add(0x31)
            special = random.choice(list(valid))
        if branch <= 9:
            # physical special
            factor = int(self.stats['level'] * 16 / 99.0) + 1
            power = random.randint(0, factor) + random.randint(0, factor)
            power = max(power, 0x00)
            power = min(power, 0x0F)
            special = 0x20 + power
        elif branch >= 10:
            # bonus special
            valid = set(range(10, 0x1F))
            valid.remove(0x1E)
            valid.remove(0x19)
            valid.add(0x0A)
            special = random.choice(list(valid))
        self.special = special

    def mutate(self):
        self.mutate_stats()
        self.mutate_items()
        self.mutate_control()
        if random.randint(1, 10) > 8:
            self.mutate_statuses()
        if random.randint(1, 10) > 8:
            self.mutate_affinities()
        if random.randint(1, 10) > 8:
            self.mutate_special()
