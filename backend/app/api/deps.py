from fastapi import Request

from app.db.session import SessionLocal
from app.services.uow import UnitOfWork


def get_uow(request: Request):
    session = SessionLocal()
    uow = UnitOfWork(session)
    request.state.uow = uow
    try:
        yield uow
        uow.commit()
    except Exception:
        uow.rollback()
        raise
    finally:
        uow.close()
