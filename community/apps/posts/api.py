from http import HTTPStatus

from django.http import HttpRequest
from ninja import Query, Router

from apps.accounts.auth import JWTAccessAuth
from apps.posts import services
from apps.posts.schemas import (
    BoardOut,
    CommentCreateIn,
    CommentOut,
    CommentReplyOut,
    PostCreateIn,
    PostDetailOut,
    PostListOut,
    PostUpdateIn,
)

router = Router(tags=["posts"])
jwt_auth = JWTAccessAuth()


@router.get("/boards", response=list[BoardOut], auth=None, summary="게시판 목록 조회")
def get_boards(request: HttpRequest):
    return services.get_active_boards()


@router.get("/posts", response=list[PostListOut], auth=None, summary="게시글 목록 조회")
def list_posts(
    request: HttpRequest,
    board_slug: str | None = Query(
        None, description="게시판 슬러그 필터 (예: free, qna)"
    ),
    search: str | None = Query(None, description="제목/본문 검색 키워드"),
    limit: int = Query(20, ge=1, le=100, description="조회 개수"),
    offset: int = Query(0, ge=0, description="시작 오프셋"),
):
    """게시글 목록을 페이징 및 필터링하여 조회한다."""
    return services.list_posts(
        board_slug=board_slug,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/posts",
    response={HTTPStatus.CREATED: PostDetailOut},
    auth=jwt_auth,
    summary="게시글 작성",
)
def create_post(request: HttpRequest, data: PostCreateIn):
    """새 게시글을 작성합니다 (로그인 인증 필수)"""
    post = services.create_post(author=request.auth, data=data)
    return HTTPStatus.CREATED, post


@router.get(
    "/posts/{int:post_id}",
    response=PostDetailOut,
    auth=None,
    summary="게시글 상세 조회",
)
def get_post(request: HttpRequest, post_id: int):
    """게시글 상세 정보를 조회하고 조회수를 1 증가시킨다."""
    return services.get_post_detail(post_id=post_id, increment_view=True)


@router.put(
    "/posts/{int:post_id}", response=PostDetailOut, auth=jwt_auth, summary="게시글 수정"
)
def update_post(request: HttpRequest, post_id: int, data: PostUpdateIn):
    """게시글을 수정합니다."""
    return services.update_post(post_id=post_id, user=request.auth, data=data)


@router.delete(
    "/posts/{int:post_id}",
    response={HTTPStatus.NO_CONTENT: None},
    auth=jwt_auth,
    summary="게시글 삭제",
)
def delete_post(request: HttpRequest, post_id: int):
    """게시글을 소프트 삭제한다."""
    services.delete_post(post_id=post_id, user=request.auth)
    return HTTPStatus.NO_CONTENT, None


# ==============================================================================
# 3. 댓글 (Comment) API
# ==============================================================================


@router.get(
    "/posts/{int:post_id}/comments",
    response=list[CommentOut],
    auth=None,
    summary="댓글 목록 조회",
)
def list_comments(request: HttpRequest, post_id: int):
    """특정 게시글의 댓글과 대댓글 조회"""
    return services.list_comments_for_post(post_id=post_id)


@router.post(
    "/posts/{int:post_id}/comments",
    response={HTTPStatus.CREATED: CommentReplyOut},
    auth=jwt_auth,
    summary="댓글/대댓글 작성",
)
def create_comment(request: HttpRequest, post_id: int, data: CommentCreateIn):
    """댓글 또는 1단계 대댓글을 작성한다."""
    comment = services.create_comment(post_id=post_id, author=request.auth, data=data)
    return HTTPStatus.CREATED, comment


@router.delete(
    "/comments/{int:comment_id}",
    response={HTTPStatus.NO_CONTENT: None},
    auth=jwt_auth,
    summary="댓글 삭제",
)
def delete_comment(request: HttpRequest, comment_id: int):
    """댓글을 소프트 삭제한다."""
    services.delete_comment(comment_id=comment_id, user=request.auth)
    return HTTPStatus.NO_CONTENT, None
