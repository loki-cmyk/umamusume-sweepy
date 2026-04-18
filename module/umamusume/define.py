from enum import Enum


class ScenarioType(Enum):
    SCENARIO_TYPE_UNKNOWN = 0
    SCENARIO_TYPE_URA = 1
    SCENARIO_TYPE_AOHARUHAI = 2
    SCENARIO_TYPE_MANT = 3
    
    def __str__(self):
        return self.name


class SupportCardType(Enum):
    SUPPORT_CARD_TYPE_UNKNOWN = 0
    SUPPORT_CARD_TYPE_SPEED = 1
    SUPPORT_CARD_TYPE_STAMINA = 2
    SUPPORT_CARD_TYPE_POWER = 3
    SUPPORT_CARD_TYPE_WILL = 4
    SUPPORT_CARD_TYPE_INTELLIGENCE = 5
    SUPPORT_CARD_TYPE_FRIEND = 6
    SUPPORT_CARD_TYPE_GROUP = 7
    SUPPORT_CARD_TYPE_NPC = 10
    
    def __str__(self):
        return self.name


class SupportCardFavorLevel(Enum):
    SUPPORT_CARD_FAVOR_LEVEL_UNKNOWN = 0
    SUPPORT_CARD_FAVOR_LEVEL_1 = 1
    SUPPORT_CARD_FAVOR_LEVEL_2 = 2
    SUPPORT_CARD_FAVOR_LEVEL_3 = 3
    SUPPORT_CARD_FAVOR_LEVEL_4 = 4
    
    def __str__(self):
        return self.name


class TrainingType(Enum):
    TRAINING_TYPE_UNKNOWN = 0
    TRAINING_TYPE_SPEED = 1
    TRAINING_TYPE_STAMINA = 2
    TRAINING_TYPE_POWER = 3
    TRAINING_TYPE_WILL = 4
    TRAINING_TYPE_INTELLIGENCE = 5
    
    def __str__(self):
        return self.name


class MotivationLevel(Enum):
    MOTIVATION_LEVEL_UNKNOWN = 0
    MOTIVATION_LEVEL_1 = 1
    MOTIVATION_LEVEL_2 = 2
    MOTIVATION_LEVEL_3 = 3
    MOTIVATION_LEVEL_4 = 4
    MOTIVATION_LEVEL_5 = 5
    
    def __str__(self):
        return self.name


class TurnOperationType(Enum):
    TURN_OPERATION_TYPE_UNKNOWN = 0
    TURN_OPERATION_TYPE_TRAINING = 1
    TURN_OPERATION_TYPE_REST = 2
    TURN_OPERATION_TYPE_MEDIC = 3
    TURN_OPERATION_TYPE_TRIP = 4
    TURN_OPERATION_TYPE_RACE = 5
    
    def __str__(self):
        return self.name
