from django.contrib.auth import get_user_model
from django.db import models

# Create your models here.

User = get_user_model()


class Board(models.Model):
    slug = models.SlugField(
        max_length=50, unique=True, help_text="게시판 영문 식별자 (ex: free, qna)"
    )
    name = models.CharField(max_length=100, help_text="게시판 표시 이름")
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "board"
        verbose_name = "게시판"
        verbose_name_plural = "게시판 목록"

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"


class Post(models.Model):
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    title = models.CharField(max_length=255)
    content = models.TextField()

    view_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    # like_count = models.PositiveIntegerField(default=0)
    is_pinned = models.BooleanField(default=False, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    # 특화 게시판을 위한 JSON 필드 (ex: Q&A 채택 답변 ID, 중고거래 가격 등)
    extra_data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "posts"
        ordering = (
            "-is_pinned",
            "-created_at",
        )
        indexes = (
            # 게시판별 목록 조회 인덱스
            models.Index(fields=["board", "is_deleted", "-created_at"]),
            # 특정 유저가 쓴 글 목록 조회 인덱스
            models.Index(fields=["author", "is_deleted", "-created_at"]),
        )

    def __str__(self) -> str:
        return self.title


class Comment(models.Model):
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replies",
    )
    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "comments"
        ordering = ("created_at",)
        indexes = (models.Index(fields=["post", "parent", "created_at"]),)

    def __str__(self) -> str:
        return f"Comment #{self.pk} on Post #{self.post_id}"
