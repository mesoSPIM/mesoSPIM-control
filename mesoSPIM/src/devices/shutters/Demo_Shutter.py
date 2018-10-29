class Demo_Shutter:
    def __init__(self, shutterline):   
        self.shutterline =  shutterline
        self.shutterstate = False

    def open(self, *args):
        self.shutterstate = True

    def close(self, *args):
        self.shutterstate = False
    
    def state(self, *args):
        return self.shutterstate

