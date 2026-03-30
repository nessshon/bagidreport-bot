from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class BaseModel(DeclarativeBase):
    __repr_cols__: tuple[str, ...] = ()
    __repr_cols_num__: int = 10

    def __repr__(self) -> str:
        cols = ", ".join(
            f"{col}={getattr(self, col)!r}"
            for idx, col in enumerate(self.__table__.columns.keys())
            if col in self.__repr_cols__ or idx < self.__repr_cols_num__
        )
        return f"<{self.__class__.__name__} {cols}>"
