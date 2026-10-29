from datetime import datetime
from typing import Any

from ninja import Schema, Field


# 게시판 DTO
class BoardOut(Schema):
    id: int
    slug: str
    name: str
    description: str


# 작성자 DTO
class AuthorOut(Schema):
    id: int
    email: str


# 게시글 DTO
class PostCreateIn(Schema):
    board_slug: str
    title: str = Field(..., max_length=255)
    content: str
    extra_data: dict[str, Any] = Field(default_factory=dict)


class PostUpdateIn(Schema):
    title: str = Field(..., max_length=255)
    content: str
    extra_data: dict[str, Any] = Field(default_factory=dict)


class PostListOut(Schema):
    id: int
    board_slug: str = Field(..., alias="board.slug")
    board_name: str = Field(..., alias="board.name")
    author: AuthorOut
    title: str
    view_count: int
    comment_count: int
    is_pinned: bool
    created_at: datetime


class PostDetailOut(Schema):
    id: int
    board_slug: str = Field(..., alias="board.slug")
    board_name: str = Field(..., alias="board.name")
    author: AuthorOut
    title: str
    content: str
    view_count: int
    extra_data: dict[str, Any]


# 댓글 DTO
class CommentCreateIn(Schema):
    content: str
    parent_id: int | None = None


class CommentReplyOut(Schema):
    id: int
    author: AuthorOut
    is_deleted: bool

    @staticmethod
    def resolve_content(obj: Any) -> str:
        if obj.is_deleted:
            return "삭제된 댓글입니다."
        return obj.content


class CommentOut(Schema):
    id: int
    author: AuthorOut
    content: str
    is_deleted: bool
    created_at: datetime
    replies: list[CommentReplyOut] = Field(default_factory=list)

    @staticmethod
    def resolve_content(obj: Any) -> str:
        if obj.is_deleted:
            return "삭제된 댓글입니다."
        return obj.content
