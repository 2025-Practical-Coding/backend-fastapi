import json
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ========== 모델 정의 ==========
@dataclass
class Relationship:
    friend: List[str]
    enemy: List[str]

@dataclass
class Character:
    name: str
    slug: str
    subtitle: str
    story: str
    region: str = ""
    affinity: int = 0
    isAlly: bool = False
    relationships: Dict[str, Relationship] = None

@dataclass
class Region:
    name: str
    characters: List[Character]

# ========== 게임 상태 ==========
class GameState:
    def __init__(self, regions: List[Region]):
        self.regions = regions
        self.convCounts: Dict[str, int] = {}
        self.currentCharacter: Optional[Character] = None
        self.convLimit = 7
        self.allies: List[Character] = []
        self.maxRounds = 1
        self.currentRound = 1
        self.affinityThreshold = 5
        self.allyThreshold = 2
        self.relationshipThreshold = 2
        self.totalRelationship = 5

    @classmethod
    def loadFromFile(cls, path1: str, path2: str) -> 'GameState':
        with open(path1, encoding='utf-8') as f:
            data = json.load(f)
        with open(path2, encoding='utf-8') as ext_f:
            extData = json.load(ext_f)
        relations = {name: Relationship(info['friends'], info['enemies']) for name, info in extData.items()}
        regions = [Region(name, [Character(**c) for c in chars]) for name, chars in data.items()]
        for region in regions:
            for char in region.characters:
                char.region = region.name
                if char.name in relations:
                    char.relationships = relations[char.name]
                else:
                    char.relationships = Relationship(friend=[], enemy=[])
        return cls(regions)

    def initialize(self):
        random.shuffle(self.regions)
        self.convCounts = {}
        self.currentRound = 1
        self.allies = []
        self.totalRelationship = 15
        self.currentCharacter = self.selectNextCharacter()


    def getRegionName(self, slug: str) -> Optional[str]:
        for region in self.regions:
            for char in region.characters:
                if char.slug == slug:
                    return region.name
        return None

    def isConversationDone(self, slug: str) -> bool:
        char = next((c for region in self.regions for c in region.characters if c.slug == slug), None)
        return not char or self.convCounts.get(slug, 0) >= self.convLimit or char.isAlly

    def selectNextCharacter(self) -> Optional[Character]:
        candidates = [
            c for region in self.regions for c in region.characters
            if self.convCounts.get(c.slug, 0) < self.convLimit and not c.isAlly
        ]
        if not candidates:
            self.currentCharacter = None
            return None
        self.currentCharacter = random.choice(candidates)
        return self.currentCharacter

    def talk(self, slug: str, name: str, affinityChange: int = 0):
        char = next((c for region in self.regions for c in region.characters if c.slug == slug), None)
        if not char or self.convCounts.get(slug, 0) >= self.convLimit:
            return
        self.convCounts[slug] = self.convCounts.get(slug, 0) + 1
        char.affinity += affinityChange
        if char.affinity >= self.affinityThreshold and not char.isAlly:
            char.isAlly = True
            self.allies.append(char)
            print(f"[DEBUG] talk() - 대상 캐릭터: {name}, affinityChange={affinityChange}")
            print(f"[DEBUG] allies 수: {len(self.allies)}")
            # 새 동료(char)와 기존 동료(ally)간 관계 계산
            for ally in self.allies:
                if ally is char:
                    continue  # 자기 자신은 제외

                # char → ally
                if ally.name in char.relationships.enemy:
                    self.totalRelationship -= 1
                if ally.name in char.relationships.friend:
                    self.totalRelationship += 1

                # ally → char
                if char.name in ally.relationships.enemy:
                    self.totalRelationship -= 1
                if char.name in ally.relationships.friend:
                    self.totalRelationship += 1

        self.currentRound += 1

    def isGameOver(self) -> bool:
        return self.currentRound > self.maxRounds or self.currentCharacter is None
