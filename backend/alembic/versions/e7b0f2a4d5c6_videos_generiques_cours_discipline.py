"""vidéos génériques, chorégraphie -> vidéos, discipline et niveau des cours

Voir spec/SPEC.md §5.3, §6.5, §6.7 et §6.8 (décisions du 2026-10-03) :
- `cours.discipline` et `cours.niveau`, pré-remplis d'après le nom du cours
  (sélecteur de l'écran Chorégraphie) ;
- le module vidéo devient générique : `videos` perd `cours_id`,
  `choregraphie_id` et `ordre`, et porte à la place son école et sa saison ;
- c'est la chorégraphie qui référence ses vidéos, par la nouvelle table
  `choregraphies_videos` (les liens existants y sont recopiés) ;
- `televersements_video` perd `cours_id`.

Revision ID: e7b0f2a4d5c6
Revises: d6a9e1f3c4b5
Create Date: 2026-10-03 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from cours.classement import classer

# revision identifiers, used by Alembic.
revision: str = 'e7b0f2a4d5c6'
down_revision: Union[str, Sequence[str], None] = 'd6a9e1f3c4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _colonnes(table: str) -> set[str]:
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _index(table: str) -> set[str]:
    return {i['name'] for i in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    connexion = op.get_bind()

    # --- Cours : discipline et niveau ---
    if 'discipline' not in _colonnes('cours'):
        op.add_column('cours', sa.Column('discipline', sa.String(length=50), nullable=True))
        op.add_column('cours', sa.Column('niveau', sa.String(length=50), nullable=True))
    for cours_id, nom in connexion.execute(sa.text("SELECT id, nom FROM cours WHERE discipline IS NULL")).all():
        discipline, niveau = classer(nom)
        connexion.execute(
            sa.text("UPDATE cours SET discipline = :d, niveau = :n WHERE id = :i"),
            {"d": discipline, "n": niveau, "i": cours_id},
        )

    # --- Chorégraphie -> vidéos ---
    # La table peut déjà exister : l'appli crée les tables manquantes à son
    # démarrage (même piège que la migration des saisons).
    if 'choregraphies_videos' not in sa.inspect(connexion).get_table_names():
        op.create_table(
            'choregraphies_videos',
            sa.Column('choregraphie_id', sa.Integer(), sa.ForeignKey('choregraphies.id'), nullable=False),
            sa.Column('video_id', sa.Integer(), sa.ForeignKey('videos.id'), primary_key=True),
            sa.Column('ordre', sa.Integer(), nullable=False, server_default='0'),
        )
        op.create_index('ix_choregraphies_videos_choregraphie_id', 'choregraphies_videos', ['choregraphie_id'])

    colonnes = _colonnes('videos')
    if 'choregraphie_id' in colonnes:
        connexion.execute(sa.text(
            "INSERT INTO choregraphies_videos (choregraphie_id, video_id, ordre) "
            "SELECT v.choregraphie_id, v.id, COALESCE(v.ordre, v.id) FROM videos v "
            "WHERE v.choregraphie_id IS NOT NULL "
            "AND v.choregraphie_id IN (SELECT id FROM choregraphies) "
            "AND v.id NOT IN (SELECT video_id FROM choregraphies_videos)"
        ))

    # --- Vidéos : école et saison à la place du cours ---
    if 'ecole_id' not in colonnes:
        op.add_column('videos', sa.Column('ecole_id', sa.Integer(), nullable=True))
        op.add_column('videos', sa.Column('saison_id', sa.Integer(), nullable=True))
    if 'cours_id' in colonnes:
        connexion.execute(sa.text(
            "UPDATE videos SET "
            "ecole_id = (SELECT c.ecole_id FROM cours c WHERE c.id = videos.cours_id), "
            "saison_id = (SELECT c.saison_id FROM cours c WHERE c.id = videos.cours_id) "
            "WHERE ecole_id IS NULL"
        ))
        # Vidéo dont le cours n'existe plus : inatteignable, et sans école
        # connue. Son lien éventuel est retiré, la ligne aussi.
        connexion.execute(sa.text(
            "DELETE FROM choregraphies_videos WHERE video_id IN (SELECT id FROM videos WHERE ecole_id IS NULL)"
        ))
        connexion.execute(sa.text(
            "UPDATE televersements_video SET video_id = NULL WHERE video_id IN (SELECT id FROM videos WHERE ecole_id IS NULL)"
        ))
        connexion.execute(sa.text("DELETE FROM videos WHERE ecole_id IS NULL"))

        index = _index('videos')
        # batch : SQLite recrée la table pour supprimer des colonnes.
        with op.batch_alter_table('videos') as batch:
            for nom in ('ix_videos_cours_id', 'ix_videos_choregraphie_id'):
                if nom in index:
                    batch.drop_index(nom)
            batch.drop_column('cours_id')
            batch.drop_column('choregraphie_id')
            batch.drop_column('ordre')
            batch.alter_column('ecole_id', existing_type=sa.Integer(), nullable=False)
            batch.alter_column('saison_id', existing_type=sa.Integer(), nullable=False)
            batch.create_foreign_key('fk_videos_ecole_id', 'ecoles', ['ecole_id'], ['id'])
            batch.create_foreign_key('fk_videos_saison_id', 'saisons', ['saison_id'], ['id'])
            batch.create_index('ix_videos_ecole_id', ['ecole_id'])
            batch.create_index('ix_videos_saison_id', ['saison_id'])

    if 'cours_id' in _colonnes('televersements_video'):
        with op.batch_alter_table('televersements_video') as batch:
            batch.drop_column('cours_id')


def downgrade() -> None:
    connexion = op.get_bind()
    with op.batch_alter_table('televersements_video') as batch:
        batch.add_column(sa.Column('cours_id', sa.Integer(), nullable=True))
    with op.batch_alter_table('videos') as batch:
        batch.add_column(sa.Column('cours_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('choregraphie_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('ordre', sa.Integer(), nullable=True))
    # Chaque vidéo reprend sa chorégraphie, et le cours de celle-ci. Une
    # vidéo sans chorégraphie n'a plus de cours connu : elle est supprimée
    # (le fichier reste sur le disque).
    connexion.execute(sa.text(
        "UPDATE videos SET "
        "choregraphie_id = (SELECT l.choregraphie_id FROM choregraphies_videos l WHERE l.video_id = videos.id), "
        "ordre = (SELECT l.ordre FROM choregraphies_videos l WHERE l.video_id = videos.id)"
    ))
    connexion.execute(sa.text(
        "UPDATE videos SET cours_id = (SELECT c.cours_id FROM choregraphies c WHERE c.id = videos.choregraphie_id)"
    ))
    connexion.execute(sa.text(
        "UPDATE televersements_video SET video_id = NULL WHERE video_id IN (SELECT id FROM videos WHERE cours_id IS NULL)"
    ))
    connexion.execute(sa.text("DELETE FROM videos WHERE cours_id IS NULL"))
    connexion.execute(sa.text(
        "UPDATE televersements_video SET cours_id = (SELECT v.cours_id FROM videos v WHERE v.id = televersements_video.video_id)"
    ))
    connexion.execute(sa.text("DELETE FROM televersements_video WHERE cours_id IS NULL"))
    with op.batch_alter_table('videos') as batch:
        batch.drop_index('ix_videos_ecole_id')
        batch.drop_index('ix_videos_saison_id')
        batch.drop_constraint('fk_videos_ecole_id', type_='foreignkey')
        batch.drop_constraint('fk_videos_saison_id', type_='foreignkey')
        batch.drop_column('ecole_id')
        batch.drop_column('saison_id')
        batch.alter_column('cours_id', existing_type=sa.Integer(), nullable=False)
        batch.create_index('ix_videos_cours_id', ['cours_id'])
        batch.create_index('ix_videos_choregraphie_id', ['choregraphie_id'])
    op.drop_table('choregraphies_videos')
    with op.batch_alter_table('cours') as batch:
        batch.drop_column('discipline')
        batch.drop_column('niveau')
