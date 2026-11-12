"""publications: the news module becomes Publications, with several blogs

spec/modules/actualites.md §12 (Seb, 12 November 2026). The module `news`
is renamed `publications` and its tables `news_*` become `pub_*`; an
organization now has one or more blogs (« Actus », « Techniques »…).

Nothing is lost. Each organization gets a blog « Actus » (with levels, no
categories) that takes its settings and all its posts; the right « Publier les
actualités » becomes « Publier dans Actus » with the same members; the module
stays on or off as it was; the Instagram link relays into Actus.

New tables are created, the rows copied with their ids (INSERT … SELECT,
portable SQL), then the old tables
dropped (a copy rather than renames: new columns, new keys, and index names
that match the models). Tables already made by `create_all` are kept (they are
empty).

Revision ID: f3b9d2a6c8e1
Revises: c8f1a3e5d7b2
Create Date: 2026-11-12 11:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3b9d2a6c8e1'
down_revision: Union[str, Sequence[str], None] = 'c8f1a3e5d7b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_RIGHT = 'right.news.publish'


def _create_tables(existing: set[str]) -> None:
    if 'pub_blogs' not in existing:
        op.create_table(
            'pub_blogs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('org_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=60), nullable=False),
            sa.Column('icon', sa.String(length=20), nullable=False),
            sa.Column('position', sa.Integer(), nullable=False),
            sa.Column('with_levels', sa.Boolean(), nullable=False),
            sa.Column('with_categories', sa.Boolean(), nullable=False),
            sa.Column('open_app_on', sa.Boolean(), nullable=False),
            sa.Column('media_first', sa.Boolean(), nullable=False),
            sa.Column('visible_to_all', sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(['org_id'], ['ecoles.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_pub_blogs_org_id', 'pub_blogs', ['org_id'])
    if 'pub_categories' not in existing:
        op.create_table(
            'pub_categories',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('blog_id', sa.Integer(), nullable=False),
            sa.Column('parent_id', sa.Integer(), nullable=True),
            sa.Column('name', sa.String(length=60), nullable=False),
            sa.ForeignKeyConstraint(['blog_id'], ['pub_blogs.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['parent_id'], ['pub_categories.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_pub_categories_blog_id', 'pub_categories', ['blog_id'])
    if 'pub_posts' not in existing:
        op.create_table(
            'pub_posts',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('org_id', sa.Integer(), nullable=False),
            sa.Column('blog_id', sa.Integer(), nullable=False),
            sa.Column('level', sa.String(length=10), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=True),
            sa.Column('category_id', sa.Integer(), nullable=True),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('on_top_until', sa.Date(), nullable=True),
            sa.Column('notify', sa.Boolean(), nullable=False),
            sa.Column('instagram_id', sa.String(length=64), nullable=True),
            sa.Column('document_id', sa.Integer(), nullable=True),
            sa.Column('notified_at', sa.DateTime(), nullable=True),
            sa.Column('author_id', sa.Integer(), nullable=True),
            sa.Column('author_name', sa.String(length=100), nullable=False),
            sa.Column('published_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['org_id'], ['ecoles.id']),
            sa.ForeignKeyConstraint(['blog_id'], ['pub_blogs.id']),
            sa.ForeignKeyConstraint(['category_id'], ['pub_categories.id']),
            sa.ForeignKeyConstraint(['document_id'], ['doc_nodes.id']),
            sa.ForeignKeyConstraint(['author_id'], ['comptes.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        for column in ('org_id', 'blog_id', 'category_id', 'instagram_id', 'published_at'):
            op.create_index(f'ix_pub_posts_{column}', 'pub_posts', [column])
    if 'pub_media' not in existing:
        op.create_table(
            'pub_media',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('post_id', sa.Integer(), nullable=False),
            sa.Column('position', sa.Integer(), nullable=False),
            sa.Column('photo_sha', sa.String(length=64), nullable=True),
            sa.Column('video_id', sa.Integer(), nullable=True),
            sa.Column('link_url', sa.String(length=2000), nullable=True),
            sa.Column('link_title', sa.String(length=300), nullable=True),
            sa.ForeignKeyConstraint(['post_id'], ['pub_posts.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['video_id'], ['videos.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_pub_media_post_id', 'pub_media', ['post_id'])
        op.create_index('ix_pub_media_video_id', 'pub_media', ['video_id'])
    if 'pub_seen' not in existing:
        op.create_table(
            'pub_seen',
            sa.Column('compte_id', sa.Integer(), nullable=False),
            sa.Column('blog_id', sa.Integer(), nullable=False),
            sa.Column('seen_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['compte_id'], ['comptes.id']),
            sa.ForeignKeyConstraint(['blog_id'], ['pub_blogs.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('compte_id', 'blog_id'),
        )
    if 'pub_instagram_settings' not in existing:
        op.create_table(
            'pub_instagram_settings',
            sa.Column('org_id', sa.Integer(), nullable=False),
            sa.Column('hashtag', sa.String(length=100), server_default='', nullable=False),
            sa.Column('publish', sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.ForeignKeyConstraint(['org_id'], ['ecoles.id']),
            sa.PrimaryKeyConstraint('org_id'),
        )
    if 'pub_instagram' not in existing:
        op.create_table(
            'pub_instagram',
            sa.Column('org_id', sa.Integer(), nullable=False),
            sa.Column('blog_id', sa.Integer(), nullable=True),
            sa.Column('token_encrypted', sa.Text(), nullable=False),
            sa.Column('username', sa.String(length=100), nullable=False),
            sa.Column('linked_by', sa.Integer(), nullable=True),
            sa.Column('linked_by_name', sa.String(length=100), nullable=False),
            sa.Column('linked_at', sa.DateTime(), nullable=False),
            sa.Column('token_refreshed_at', sa.DateTime(), nullable=False),
            sa.Column('ig_user_id', sa.String(length=40), nullable=True),
            sa.Column('refreshes', sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column('last_sync_at', sa.DateTime(), nullable=True),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(['org_id'], ['ecoles.id']),
            sa.ForeignKeyConstraint(['blog_id'], ['pub_blogs.id']),
            sa.ForeignKeyConstraint(['linked_by'], ['comptes.id']),
            sa.PrimaryKeyConstraint('org_id'),
        )


def _rows(conn, table: str, existing: set[str]) -> list[dict]:
    if table not in existing:
        return []
    return [dict(r._mapping) for r in conn.execute(sa.text(f'SELECT * FROM {table}'))]


def upgrade() -> None:
    conn = op.get_bind()
    existing = set(sa.inspect(conn).get_table_names())
    _create_tables(existing)
    meta = sa.MetaData()
    meta.reflect(bind=conn, only=['pub_blogs', 'pub_instagram_settings', 'groups', 'org_modules'])
    t = meta.tables

    # One blog « Actus » per organization, with its settings.
    settings = {r['org_id']: r for r in _rows(conn, 'news_settings', existing)}
    actus = {}
    for (org_id,) in conn.execute(sa.text('SELECT id FROM ecoles ORDER BY id')):
        s = settings.get(org_id, {})
        result = conn.execute(t['pub_blogs'].insert().values(
            org_id=org_id, name='Actus', icon='news', position=0, with_levels=True, with_categories=False,
            open_app_on=bool(s.get('open_on_news', True)), media_first=bool(s.get('media_first', False)),
            visible_to_all=bool(s.get('visible_to_all', True)),
        ))
        actus[org_id] = result.inserted_primary_key[0]
        if s:
            conn.execute(t['pub_instagram_settings'].insert().values(
                org_id=org_id, hashtag=s.get('instagram_hashtag') or '', publish=bool(s.get('instagram_publish', True)),
            ))

    # Posts, media, « Nouveau », Instagram: same ids, into Actus (each
    # organization has exactly one blog at this point). Copied in SQL, so
    # that dates go through as they are.
    blog_of = '(SELECT b.id FROM pub_blogs b WHERE b.org_id = {}.org_id)'
    if 'news_items' in existing:
        columns = ('id, org_id, level, body, on_top_until, notify, instagram_id, document_id, notified_at, author_id, '
                   'author_name, published_at, created_at, updated_at')
        conn.execute(sa.text(f'INSERT INTO pub_posts ({columns}, blog_id) '
                             f'SELECT {columns}, {blog_of.format("news_items")} FROM news_items'))
    if 'news_media' in existing:
        conn.execute(sa.text('INSERT INTO pub_media (id, post_id, position, photo_sha, video_id, link_url, link_title) '
                             'SELECT id, item_id, position, photo_sha, video_id, link_url, link_title FROM news_media'))
    if 'news_seen' in existing:
        conn.execute(sa.text('INSERT INTO pub_seen (compte_id, blog_id, seen_at) '
                             'SELECT s.compte_id, b.id, s.seen_at FROM news_seen s '
                             'JOIN comptes c ON c.id = s.compte_id JOIN pub_blogs b ON b.org_id = c.ecole_id'))
    if 'news_instagram' in existing:
        columns = ('org_id, token_encrypted, username, linked_by, linked_by_name, linked_at, token_refreshed_at, '
                   'ig_user_id, refreshes, last_sync_at, last_error')
        conn.execute(sa.text(f'INSERT INTO pub_instagram ({columns}, blog_id) '
                             f'SELECT {columns}, {blog_of.format("news_instagram")} FROM news_instagram'))

    # The right: same groups and members, now the right of the blog Actus.
    groups = t['groups']
    for org_id, blog_id in actus.items():
        conn.execute(groups.update().where(groups.c.org_id == org_id, groups.c.key == OLD_RIGHT).values(
            key=f'right.publications.publish.{blog_id}', name='Publier dans Actus'))
    # The module keeps its state (on or off) under its new key.
    modules = t['org_modules']
    conn.execute(modules.update().where(modules.c.module_key == 'news').values(module_key='publications'))

    for table in ('news_media', 'news_seen', 'news_instagram', 'news_settings', 'news_items'):
        if table in existing:
            op.drop_table(table)


def downgrade() -> None:
    """Back to one news page per organization: every post goes back, titles
    and categories are lost, the first blog gives its settings and its right."""
    conn = op.get_bind()
    op.create_table(
        'news_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('level', sa.String(length=10), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('on_top_until', sa.Date(), nullable=True),
        sa.Column('notify', sa.Boolean(), nullable=False),
        sa.Column('notified_at', sa.DateTime(), nullable=True),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('author_name', sa.String(length=100), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('instagram_id', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['doc_nodes.id'], name='fk_news_items_document_id'),
        sa.ForeignKeyConstraint(['org_id'], ['ecoles.id']),
        sa.ForeignKeyConstraint(['author_id'], ['comptes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    for column in ('org_id', 'published_at', 'instagram_id'):
        op.create_index(f'ix_news_items_{column}', 'news_items', [column])
    op.create_table(
        'news_media',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('photo_sha', sa.String(length=64), nullable=True),
        sa.Column('video_id', sa.Integer(), nullable=True),
        sa.Column('link_url', sa.String(length=2000), nullable=True),
        sa.Column('link_title', sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['news_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_news_media_item_id', 'news_media', ['item_id'])
    op.create_index('ix_news_media_video_id', 'news_media', ['video_id'])
    op.create_table(
        'news_seen',
        sa.Column('compte_id', sa.Integer(), nullable=False),
        sa.Column('seen_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['compte_id'], ['comptes.id']),
        sa.PrimaryKeyConstraint('compte_id'),
    )
    op.create_table(
        'news_settings',
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('open_on_news', sa.Boolean(), nullable=False),
        sa.Column('media_first', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('visible_to_all', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('instagram_hashtag', sa.String(length=100), server_default='', nullable=False),
        sa.Column('instagram_publish', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['ecoles.id']),
        sa.PrimaryKeyConstraint('org_id'),
    )
    op.create_table(
        'news_instagram',
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('token_encrypted', sa.Text(), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('linked_by', sa.Integer(), nullable=True),
        sa.Column('linked_by_name', sa.String(length=100), nullable=False),
        sa.Column('linked_at', sa.DateTime(), nullable=False),
        sa.Column('token_refreshed_at', sa.DateTime(), nullable=False),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('ig_user_id', sa.String(length=40), nullable=True),
        sa.Column('refreshes', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.ForeignKeyConstraint(['linked_by'], ['comptes.id']),
        sa.ForeignKeyConstraint(['org_id'], ['ecoles.id']),
        sa.PrimaryKeyConstraint('org_id'),
    )
    columns = ('id, org_id, level, body, on_top_until, notify, notified_at, author_id, author_name, published_at, '
               'created_at, updated_at, document_id, instagram_id')
    conn.execute(sa.text(f'INSERT INTO news_items ({columns}) SELECT {columns} FROM pub_posts'))
    conn.execute(sa.text('INSERT INTO news_media (id, item_id, position, photo_sha, video_id, link_url, link_title) '
                         'SELECT id, post_id, position, photo_sha, video_id, link_url, link_title FROM pub_media'))
    conn.execute(sa.text('INSERT INTO news_seen (compte_id, seen_at) SELECT compte_id, MAX(seen_at) FROM pub_seen GROUP BY compte_id'))
    columns = ('org_id, token_encrypted, username, linked_by, linked_by_name, linked_at, token_refreshed_at, '
               'last_sync_at, last_error, ig_user_id, refreshes')
    conn.execute(sa.text(f'INSERT INTO news_instagram ({columns}) SELECT {columns} FROM pub_instagram'))
    first = {}
    for blog_id, org_id in conn.execute(sa.text('SELECT id, org_id FROM pub_blogs ORDER BY position DESC, id DESC')):
        first[org_id] = blog_id
    for org_id, blog_id in first.items():
        conn.execute(sa.text(
            'INSERT INTO news_settings (org_id, open_on_news, media_first, visible_to_all, instagram_hashtag, instagram_publish) '
            "SELECT b.org_id, b.open_app_on, b.media_first, b.visible_to_all, COALESCE(s.hashtag, ''), COALESCE(s.publish, 1) "
            'FROM pub_blogs b LEFT JOIN pub_instagram_settings s ON s.org_id = b.org_id WHERE b.id = :b'), {'b': blog_id})
        conn.execute(sa.text("UPDATE groups SET key = :old, name = 'Publier les actualités' WHERE org_id = :o AND key = :k"),
                     {'old': OLD_RIGHT, 'o': org_id, 'k': f'right.publications.publish.{blog_id}'})
    conn.execute(sa.text("DELETE FROM group_members WHERE group_id IN (SELECT id FROM groups WHERE key LIKE 'right.publications.publish.%')"))
    conn.execute(sa.text("DELETE FROM groups WHERE key LIKE 'right.publications.publish.%'"))
    conn.execute(sa.text("UPDATE org_modules SET module_key = 'news' WHERE module_key = 'publications'"))
    for table in ('pub_seen', 'pub_media', 'pub_instagram', 'pub_instagram_settings', 'pub_posts', 'pub_categories', 'pub_blogs'):
        op.drop_table(table)
