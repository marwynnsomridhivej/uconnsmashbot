import random


__all__ = (
    "get_random_object",
    "get_random_body_part",
)


obj_list = [
    'a banana',
    'a baseball',
    'a beach ball',
    'a blanket',
    'a boomerang',
    'a bunch of grapes',
    'a computer out the window',
    'a couch',
    'a discus',
    'a football',
    'a fridge at their neighbor',
    'a frustratingly long book',
    'a knife',
    'a loaded gun instead of shooting it',
    'a paper airplane',
    'a plate',
    'a pool ball',
    'a samurai sword',
    'a sharp stone',
    'a shot put',
    'a singular grape',
    'a spear',
    'a stuffed toad plushie',
    'a trident',
    'a water polo ball',
    'an apple',
    'an error',
    'an exception',
    'an orange',
    'away the trash',
    'away their chances at a relationship',
    'some dice',
    'some eggs',
    'some hands',
    'some poop',
    'some water balloons',
    'their last brain cell out the window',
    'their phone at the wall',
]

parts_list = [
    'ankle',
    'arm',
    'chest',
    'elbow',
    'face',
    'foot',
    'forehead',
    'hand',
    'head',
    'knee',
    'leg',
    'neck',
    'nose',
    'shoulder',
    'stomach',
    'toe',
]


def get_random_object():
    return random.choice(obj_list)


def get_random_body_part():
    return random.choice(parts_list)