
class SceneMessage:
    def __init__(self, d):
        """ Construct with dictionary magic; each field in the dict is now that of an Object. """
        self.__dict__ = d



class AdministrativeMessage:
    def __init__(self, functionCall='off', value=''):
        self.functionCall = functionCall
        self.value = value
