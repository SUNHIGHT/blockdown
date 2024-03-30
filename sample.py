# CharacterBaseクラスの定義。すべてのキャラクターがこのクラスから派生します。
class CharacterBase:
    # コンストラクタで名前、HP（ヒットポイント）、攻撃力を設定します。
    def __init__(self, name, hp, attack_power):
        self.name = name
        self.hp = hp
        self.attack_power = attack_power

    # 他のキャラクターに対する攻撃メソッド。
    def attack(self, other_character):
        other_character.receive_damage(self.attack_power)

    # ダメージを受け入れるメソッド。
    def receive_damage(self, damage):
        self.hp -= damage  # HPからダメージ量を引く。
        print(f'{self.name} received {damage} damage!')
        if self.hp <= 0:  # もしHPが0以下なら、キャラクターは倒される。
            print(f'{self.name} has been defeated!')

# Heroクラスの定義。CharacterBaseクラスから派生します。
class Hero(CharacterBase):
    # デフォルトの名前、HP、攻撃力を設定します。
    def __init__(self, name='Hero', hp=100, attack_power=10):
        super().__init__(name, hp, attack_power)

# Monsterクラスの定義。CharacterBaseクラスから派生します。
class Monster(CharacterBase):
    # デフォルトの名前、HP、攻撃力を設定します。
    def __init__(self, name='Monster', hp=50, attack_power=5):
        super().__init__(name, hp, attack_power)
        