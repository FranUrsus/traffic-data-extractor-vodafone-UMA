import os
from mongo_manager import RepositoryBase
from mongo.entity.graph import Graph


class RepositorioGraphSoho(RepositoryBase[Graph]):
    def __init__(self):
        super().__init__(os.getenv('MONGO_COLLECTION_GRAPHS_SOHO'), Graph)
