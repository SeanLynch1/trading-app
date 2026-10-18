from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from config import DATABASE_URL                   # where the database is (local Docker now, AWS RDS later)

engine = create_async_engine(                     # one shared pool of database connections for the whole program
    DATABASE_URL,
    pool_pre_ping=True,                           # check a connection still works before using it (e.g. after a restart)
)

Session = async_sessionmaker(                     # call Session() to start a unit of work: reads, writes, then commit
    engine,
    expire_on_commit=False,                       # keep objects usable after commit, so we can still return them as JSON
)
