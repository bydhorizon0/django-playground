from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Prefetch, Q, QuerySet
from ninja.errors import HttpError

from apps.posts.models import Board, Comment, Post
from apps.posts.schemas import CommentCreateIn, PostCreateIn, PostUpdateIn

User = get_user_model()


# ==============================================================================
# 게시판 (Board) 서비스
# ==============================================================================
def get_active_boards() -> QuerySet[Board]:
    """활성화된 게시판 목록을 반환한다."""
    return Board.objects.filter(is_active=True).order_by("id")


def get_board_by_slug(slug: str) -> Board:
    """slug로 활성화된 게시판을 조회한다."""
    board = Board.objects.filter(slug=slug, is_active=True).first()
    if board is None:
        raise HttpError(HTTPStatus.NOT_FOUND, f"'{slug}' 게시판을 찾을 수 없습니다.")
    return board


# ==============================================================================
# 게시글 (Post) 서비스
# ==============================================================================
def list_posts(
    *,
    board_slug: str | None = None,
    search: str | None = None,
    limit=20,
    offset=0,
) -> QuerySet[Post]:
    """게시글 목록 조회"""
    queryset = (
        Post.objects.filter(is_deleted=False)
        .select_related("author", "board")
        .order_by("-is_pinned", "-created_at")
    )

    if board_slug:
        queryset = queryset.filter(board__slug=board_slug)

    if search:
        queryset = queryset.filter(
            Q(title__icontains=search) | Q(body__icontains=search)
        )

    return queryset[offset : offset + limit]


def get_post_detail(post_id: int, *, increment_view=True) -> Post:
    """게시글 상세 조회 및 원자적(Atomic) 조회수 증가 수행"""
    post = (
        Post.objects.filter(pk=post_id, is_deleted=False)
        .select_related("author", "board")
        .first()
    )
    if post is None:
        raise HttpError(HTTPStatus.NOT_FOUND, "게시글을 찾을 수 없습니다.")

    if increment_view:
        Post.objects.filter(pk=post.pk).update(view_count=F("view_count") + 1)
        post.view_count += 1

    return post


def create_post(author: User, data: PostCreateIn) -> Post:
    """새 게시글을 작성합니다."""
    board = get_board_by_slug(data.board_slug)

    post = Post.objects.create(
        board=board,
        author=author,
        title=data.title,
        content=data.content,
        extra_data=data.extra_data,
    )
    return post


def update_post(post_id: int, user: User, data: PostUpdateIn) -> Post:
    """게시글 수정 (작성자 본인 검증)"""
    post = (
        Post.objects.filter(pk=post_id, is_deleted=False)
        .select_related("author", "board")
        .first()
    )
    if post is None:
        raise HttpError(HTTPStatus.NOT_FOUND, "게시글을 찾을 수 없습니다.")

    # 권한 검증: 작성자 본인 또는 관리자만 수정 가능
    if post.author_id != user.pk and not user.is_superuser:
        raise HttpError(HTTPStatus.FORBIDDEN, "게시글 수정 권한이 없습니다.")

    post.title = data.title
    post.content = data.content
    post.extra_data = data.extra_data
    post.save(update_fields=["title", "content", "extra_data", "updated_at"])
    return post


def delete_post(post_id: int, user: User) -> None:
    """게시글을 소프트 삭제  처리한다 (작성자 본인 검증)."""
    post = Post.objects.filter(id=post_id, is_deleted=False).first()
    if post is None:
        raise HttpError(HTTPStatus.NOT_FOUND, "게시글을 찾을 수 없습니다.")

    if post.author_id != user.pk and not user.is_superuser:
        raise HttpError(HTTPStatus.FORBIDDEN, "게시글 삭제 권한이 없습니다.")

    post.is_deleted = True
    post.save(update_fields=["is_deleted", "updated_at"])


# ==============================================================================
# 댓글 (Comment) 서비스
# ==============================================================================
def list_comments_for_post(post_id: int) -> QuerySet[Comment]:
    """원댓글과 1단계 대댓글 목록을 2번의 쿼리로 완전 해소하여 조회 (Prefetch 활용)"""
    # 게시글 존재 여부 검증
    if not Post.objects.filter(pk=post_id, is_deleted=False).exists():
        raise HttpError(HTTPStatus.NOT_FOUND, "게시글을 찾을 수 없습니다.")

    replies_prefetch = Prefetch(
        "replies",
        queryset=Comment.objects.select_related("author").order_by("created_at"),
    )

    comments = (
        Comment.objects.filter(post_id=post_id, parent=None)
        .select_related("author")
        .prefetch_related(replies_prefetch)
        .order_by("created_at")
    )

    return comments


@transaction.atomic
def create_comment(post_id: int, author: User, data: CommentCreateIn) -> Comment:
    """댓글 또는 1단계 대댓글을 작성하고 게시글 comment_count를 원자적으로 갱신한다."""
    post = Post.objects.select_for_update().filter(pk=post_id, is_deleted=False).first()
    if post is None:
        raise HttpError(HTTPStatus.NOT_FOUND, "게시글을 찾을 수 없습니다.")

    parent: Comment | None = None
    if data.parent_id is not None:
        parent = Comment.objects.filter(pk=data.parent_id, post_id=post.pk).first()
        if parent is None:
            raise HttpError(HTTPStatus.NOT_FOUND, "부모 댓글을 찾을 수 없습니다.")

        # 1-depth 제한 검증: 대댓글의 대댓글(2단계 이상) 방지
        if parent.parent_id is not None:
            raise HttpError(
                HTTPStatus.BAD_REQUEST, "대댓글에는 추가 답글을 작성할 수 없습니다."
            )

    comment = Comment.objects.create(
        post=post,
        author=author,
        parent=parent,
        content=data.content,
    )

    # Post 카운터 캐시 원자적 1 증가
    Post.objects.filter(pk=post_id).update(comment_count=F("comment_count") + 1)

    return comment


@transaction.atomic
def delete_comment(comment_id: int, user: User) -> None:
    """댓글을 소프트 삭제하고 comment_count를 원자적으로 차감"""
    comment = (
        Comment.objects.select_related("post")
        .filter(pk=comment_id, is_deleted=False)
        .first()
    )
    if comment is None:
        raise HttpError(HTTPStatus.NOT_FOUND, "댓글을 찾을 수 없습니다.")

    if comment.author_id != user.pk and not user.is_superuser:
        raise HttpError(HTTPStatus.FORBIDDEN, "댓글 삭제 권한이 없습니다.")

    comment.is_deleted = True
    comment.save(update_fields=["is_deleted", "updated_at"])

    # 댓글 수 1 감소 (0 미만으로 내려가지 않도록 안전하게 차감)
    Post.objects.filter(pk=comment.post_id, comment_count__gt=0).update(
        comment_count=F("comment_count") - 1,
    )
