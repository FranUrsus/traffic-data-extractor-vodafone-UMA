from mongo_manager import ObjetoMongoAbstract


class Graph(ObjetoMongoAbstract):

    def __init__(self, filename, datetime,
                 hour_minute_string, hour_int,
                 minute_int, day_of_week, hour_float,
                 links, automated, _id=None, **kwargs):
        super().__init__(_id=_id, **kwargs)
        self.filename = filename
        self.datetime = datetime
        self.hour_minute_string = hour_minute_string
        self.hour_int = hour_int
        self.minute_int = minute_int
        self.day_of_week = day_of_week
        self.hour_float = hour_float
        self.automated = automated
        self.links = links

    def __str__(self):
        return f'{self.datetime}: {self.links} '

