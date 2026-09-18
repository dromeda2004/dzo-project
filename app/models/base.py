# Placeholder — real ORM models go here (or in per-domain files: user.py, restaurant.py,
# menu.py, order.py, delivery.py, driver.py, payment.py, rating.py, promotion.py), per
# the core DB schema outlined in docs/DZO_TECH_ROADMAP.md Epic 1.
#
# Example shape once schema work starts:
#
# from sqlalchemy import String
# from sqlalchemy.orm import Mapped, mapped_column
# from app.core.database import Base
#
# class User(Base):
#     __tablename__ = "users"
#     id: Mapped[int] = mapped_column(primary_key=True)
#     email: Mapped[str] = mapped_column(String, unique=True, index=True)
