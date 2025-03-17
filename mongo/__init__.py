from dotenv import load_dotenv
import os
from mongo_manager import MongoManager

load_dotenv()

if os.getenv('MACHINE') == 'Fran':
    MONGO_URI = os.getenv("MONGO_URI")
    DATABASE_STEP = os.getenv("MONGO_DB")
    db = MongoManager(authenticated=False, db=DATABASE_STEP, bd_online=True, url_online=MONGO_URI)
elif os.getenv('MACHINE') == 'Juan':
    db = MongoManager(username=os.getenv('MONGO_USERNAME'),
                      password=os.getenv('MONGO_PASSWORD'),
                      auth_source=os.getenv('MONGO_AUTH_SOURCE'),
                      db=os.getenv('MONGO_DB'),
                      port_local=int(os.getenv('MONGO_PORT')))
else:
    MONGO_URI = os.getenv("MONGO_URI")
    DATABASE_STEP = os.getenv("MONGO_DB")
    db = MongoManager(authenticated=False, db=DATABASE_STEP, bd_online=True, url_online=MONGO_URI)