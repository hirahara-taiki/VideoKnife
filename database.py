import os
import shutil
from typing import Optional, Tuple
import cv2
import pandas as pd
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import Column
from sqlalchemy.types import Integer, String, Boolean
from sqlalchemy import create_engine, ForeignKey
from sqlalchemy.orm import Session, relationship
from sqlalchemy.sql import func, select, join


Base = declarative_base()


class VideoTable(Base):
    """動画の情報を保存するレコード

    Attributes:
        id_video (int): 動画ファイルのID
        name_video (str): 動画ファイルの名前
    """
    __tablename__ = "videos"
    id_video = Column(Integer, primary_key=True)
    name_video = Column(String, nullable=False, index=True)

    definitions = relationship("CropDefinitionTable", backref="videos")


class CropDefinitionTable(Base):
    """動画切り出しの定義を保存するレコード

    Attributes:
        id_definition (int): 定義のID
        id_video (int): 動画のID
        description (str): 定義の説明
        done (bool): 切り出しが完了したかどうか
        index_start (int): 切り出し開始フレーム
        index_end (int): 切り出し終了フレーム
        step_index (int): 切り出しフレーム間隔
        pixel_left (int): 切り出し矩形の左側の座標
        pixel_top (int): 切り出し矩形の上側の座標
        pixel_right (int): 切り出し矩形の右側の座標
        pixel_bottom (int): 切り出し矩形の下側の座標
    """
    __tablename__ = "crop_definitions"
    id_definition = Column(Integer, primary_key=True)
    id_video = Column(Integer, ForeignKey("videos.id_video"), nullable=False, index=True)
    description = Column(String, default="")
    done = Column(Boolean, nullable=False)
    index_start = Column(Integer, nullable=False)
    index_end = Column(Integer, nullable=False)
    step_index = Column(Integer, nullable=False)
    pixel_left = Column(Integer, nullable=True)
    pixel_top = Column(Integer, nullable=True)
    pixel_right = Column(Integer, nullable=True)
    pixel_bottom = Column(Integer, nullable=True)

    images = relationship("ImageTable", backref="crop_definitions")


class ImageTable(Base):
    """画像の情報を保存するレコード

    Attributes:
        id_image (int): 画像のID
        id_definition (int): 切り出し定義のID
        name_image (str): 画像ファイルの名前
        index_in_definition (int): 切り出し定義内で付与される画像のインデックス
    """
    __tablename__ = "images"
    id_image = Column(Integer, primary_key=True)
    id_definition = Column(Integer, ForeignKey("crop_definitions.id_definition"), nullable=False, index=True)
    name_image = Column(String, nullable=False, index=True)
    index_in_definition = Column(Integer, nullable=False)


class Album:
    def __init__(self, dir_album: str):
        """アルバムを新規作成,または,読み込みします

        Args:
            dir_album (str): アルバムのディレクトリ
        """
        self.dir_album = os.path.abspath(dir_album)
        self.dir_video = os.path.join(self.dir_album, "video")
        self.dir_image = os.path.join(self.dir_album, "image")
        self.path_db = os.path.join(self.dir_album, "base.db")
        self.url = f"sqlite:///{self.path_db}?charset=utf8"
        if not os.path.exists(dir_album):
            os.makedirs(self.dir_album)
            os.makedirs(self.dir_video)
            os.makedirs(self.dir_image)
            self.engine = create_engine(self.url)
            Base.metadata.create_all(bind=self.engine)
        else:
            self.engine = create_engine(self.url)

        session = Session(self.engine)

        max_id_video, *_ = session.query(func.max(VideoTable.id_video)).one()
        self.max_id_video: int = -1 if max_id_video is None else max_id_video

        max_id_definition, *_ = session.query(func.max(CropDefinitionTable.id_definition)).one()
        self.max_id_definition: int = -1 if max_id_definition is None else max_id_definition

        max_id_image, *_ = session.query(func.max(ImageTable.id_image)).one()
        self.max_id_image: int = -1 if max_id_image is None else max_id_image

        session.close()


    def add_video(self, path_video: str, *, move: bool = False) -> int:
        """動画をアルバムに追加します。

        Args:
            path_video (str): 動画ファイルへのパス
            move (bool, optional): Trueにすると動画を複製せずに移動します. Defaults to False.

        Raises:
            FileNotFoundError: 動画ファイルが存在しません

        Returns:
            int: 追加したファイルのIDを返します
        """
        if not os.path.exists(path_video):
            raise FileNotFoundError(f"ファイルが存在しません: {path_video}")
        name = os.path.basename(path_video)

        session = Session(self.engine)
        _name = name
        _idx = 1
        while session.query(VideoTable).filter(VideoTable.name_video == _name).all():
            _name = name[:name.rfind(".")] + f"({_idx})" + name[name.rfind("."):]
            _idx += 1
        name = _name

        path_video_dst = os.path.join(self.dir_video, name)
        if move:
            shutil.move(path_video, path_video_dst)
        else:
            shutil.copyfile(path_video, path_video_dst)

        self.max_id_video += 1
        id_video = self.max_id_video
        session.add(VideoTable(id_video=id_video, name_video=name))
        session.commit()

        session.close()
        return id_video

    def remove_video(self, id_video: int) -> bool:
        """動画をアルバムから削除します。関連する定義や画像も全て削除します。

        Args:
            id_video (int): 動画のID

        Returns:
            bool: 削除に成功した場合はTrueを返します。
        """
        session = Session(self.engine)

        video = session.query(VideoTable).filter(VideoTable.id_video == id_video).first()
        if video is None:
            session.close()
            raise FileNotFoundError(f"その動画IDは存在しません: {id_video}")

        ids_defiinition = [
            definition.id_definition
            for definition in session.query(CropDefinitionTable).filter(CropDefinitionTable.id_video == id_video).all()
        ]

        for id_definition in ids_defiinition:
            self.remove_crop_definition(id_definition)

        path_video = os.path.join(self.dir_video, video.name_video)
        os.remove(path_video)
        session.delete(video)

        session.commit()
        session.close()
        return True

    def add_crop_definition(self, id_video: int, slice: Tuple[int, int, int], rect: Optional[Tuple[int, int, int, int]] = None, description: str = "") -> int:
        """切り出し定義を追加します

        Args:
            id_video (int): 対応する動画ID。
            slice (Tuple[int, int, int]): 動画の切り出しフレーム。[開始フレーム, 終了フレーム, フレーム間隔]
            rect (Optional[Tuple[int, int, int, int]], optional): 動画内での切り出し矩形. 全体の場合はNone. Defaults to None.
            description (str, optional): 切り出し定義の説明. Defaults to "".

        Raises:
            FileNotFoundError: 動画IDが存在しません

        Returns:
            int: 切り出し定義のID
        """
        # TODO: エラーチェック: 作成済み, 矩形サイズ, slice範囲
        session = Session(self.engine)

        if not session.query(VideoTable).filter(VideoTable.id_video == id_video).all():
            session.close()
            raise FileNotFoundError(f"この動画IDは存在しません: {id_video}")

        self.max_id_definition += 1
        id_definition = self.max_id_definition
        if rect is None:
            session.add(CropDefinitionTable(
                id_definition=id_definition,
                id_video=id_video,
                description=description,
                done=False,
                index_start=slice[0],
                index_end=slice[1],
                step_index=slice[2],
            ))
        else:
            session.add(CropDefinitionTable(
                id_definition=id_definition,
                id_video=id_video,
                description=description,
                done=False,
                index_start=slice[0],
                index_end=slice[1],
                step_index=slice[2],
                pixel_left=rect[0],
                pixel_top=rect[1],
                pixel_right=rect[2],
                pixel_bottom=rect[3]
            ))
        session.commit()
        session.close()

        return id_definition

    def remove_crop_definition(self, id_definition: int) -> bool:
        """切り出し定義を削除します。付随する画像も削除されます。

        Args:
            id_definition (int): 切り出し定義のID

        Raises:
            FileNotFoundError: 切り出し定義のIDが存在しない

        Returns:
            bool: 削除に成功したかどうか
        """
        session = Session(self.engine)

        definition = session.query(CropDefinitionTable).filter(CropDefinitionTable.id_definition == id_definition).first()
        if definition is None:
            session.close()
            raise FileNotFoundError(f"この切り出し定義IDは存在しません: {id_definition}")

        if definition.done:
            images = session.query(ImageTable).filter(ImageTable.id_definition == id_definition).all()
            for image in images:
                name_image = image.name_image
                path_image = os.path.join(self.dir_image, name_image)
                if os.path.exists(path_image):
                    os.remove(path_image)
                session.delete(image)

        session.delete(definition)

        session.commit()
        session.close()
        return True

    def do_crop(self, id_definition: int) -> bool:
        """動画の切り出しを実行する

        Args:
            id_definition (int): 定義のID

        Raises:
            FileNotFoundError: 切り出し定義IDが存在しません

        Returns:
            bool: 成功したかどうか
        """
        session = Session(self.engine)

        definition = session.query(CropDefinitionTable).filter(CropDefinitionTable.id_definition == id_definition).first()
        if definition is None:
            session.close()
            raise FileNotFoundError(f"この切り出し定義IDは存在しません: {id_definition}")
        if definition.done:
            return True

        video = session.query(VideoTable).filter(VideoTable.id_video == definition.id_video).one()
        path_video = os.path.join(self.dir_video, video.name_video)

        cap = cv2.VideoCapture(path_video)
        if not cap.isOpened():
            raise RuntimeError(f"動画が開ません: name={path_video}")
        num_frame_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        rect = (0, 0, width, height)
        if definition.pixel_left is not None:
            rect = (
                max(rect[0], definition.pixel_left),
                max(rect[1], definition.pixel_top),
                min(rect[2], definition.pixel_right),
                min(rect[3], definition.pixel_bottom),
            )
        if rect[2] <= rect[0] or rect[3] <= rect[1]:
            cap.release()
            session.close()
            raise RuntimeError(f"矩形で切り出す範囲が0px以下になっています")

        idx_start = definition.index_start
        idx_end = min(definition.index_end, num_frame_total)
        step = definition.step_index
        if idx_start < 0 or step < 1:
            cap.release()
            session.close()
            raise RuntimeError(f"切り出しフレーム番号の指定が不正です")

        id_image_tmp = self.max_id_image
        try:
            for it, idx in enumerate(range(idx_start, idx_end, step)):
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                success, img = cap.read()
                if not success:
                    continue
                img = img[rect[1]:rect[3], rect[0]:rect[2]].copy()
                name_img = f"{definition.id_video:0>6d}_{idx:0>8d}_{rect[0]:0>4d},{rect[1]:0>4d},{rect[2]:0>4d},{rect[3]:0>4d}.jpg"
                _name_img = name_img
                _idx = 1
                while session.query(ImageTable).filter(ImageTable.name_image == _name_img).all():
                    _name_img = name_img[:name_img.rfind(".")] + f"({_idx})" + name_img[name_img.rfind("."):]
                    _idx += 1
                name_img = _name_img
                path_img = os.path.join(self.dir_image, name_img)
                success = cv2.imwrite(path_img, img)
                if not success:
                    continue
                self.max_id_image += 1
                id_image = self.max_id_image
                session.add(ImageTable(
                    id_image=id_image,
                    id_definition=id_definition,
                    name_image=name_img,
                    index_in_definition=it,
                ))
            definition.done = True
        except:
            self.max_id_image = id_image_tmp
            session.rollback()

        cap.release()
        session.commit()
        session.close()
        return True

    def do_crop_all(self) -> bool:
        """切り出していない全ての定義に対して切り出しを実行する

        Returns:
            bool: 全ての画像の切り出しに成功
        """
        session = Session(self.engine)
        ids_definition = [
            definition.id_definition
            for definition
            in session.query(CropDefinitionTable).filter(CropDefinitionTable.done == False).all()
        ]
        session.close()
        for id_definition in ids_definition:
            self.do_crop(id_definition)
        return True

    def get_all_video(self) -> pd.DataFrame:
        """格納されている全ての動画の情報を参照します

        Returns:
            pd.DataFrame: 結果を格納したデータフレーム
        """
        sql_statement = select(VideoTable)
        return pd.read_sql_query(sql=sql_statement, con=self.engine)

    def get_all_crop_definitions(self) -> pd.DataFrame:
        """格納されている全ての切り出し定義の情報を参照します

        Returns:
            pd.DataFrame: 結果を格納したデータフレーム
        """
        sql_statement = select(CropDefinitionTable)
        return pd.read_sql_query(sql=sql_statement, con=self.engine)

    def get_crop_definitions(self, id_video: int) -> pd.DataFrame:
        """動画に紐づいた全ての切り出し定義の情報を参照します

        Args:
            id_video (int): クエリする動画のID

        Returns:
            pd.DataFrame: 結果を格納したデータフレーム
        """
        sql_statement = select(CropDefinitionTable).filter(CropDefinitionTable.id_video == id_video)
        return pd.read_sql_query(sql=sql_statement, con=self.engine)

    def get_crop_definition(self, id_definition: int) -> pd.DataFrame:
        """動画に紐づいた全ての切り出し定義の情報を参照します

        Args:
            id_definition (int): クエリする定義のID

        Returns:
            pd.DataFrame: 結果を格納したデータフレーム
        """
        sql_statement = select(CropDefinitionTable).filter(CropDefinitionTable.id_definition == id_definition)
        return pd.read_sql_query(sql=sql_statement, con=self.engine)

    def get_all_images(self) -> pd.DataFrame:
        """格納されている全ての画像の情報を参照します

        Returns:
            pd.DataFrame: 結果を格納したデータフレーム
        """
        sql_statement = select(ImageTable)
        return pd.read_sql_query(sql=sql_statement, con=self.engine)

    def get_video_images(self, id_video: int) -> pd.DataFrame:
        """動画に紐づいた全ての画像の情報を参照します

        Args:
            id_video (int): クエリする動画のID

        Returns:
            pd.DataFrame: 結果を格納したデータフレーム
        """
        sql_statement = select(ImageTable).select_from(join(ImageTable, CropDefinitionTable)).filter(CropDefinitionTable.id_video == id_video)
        return pd.read_sql_query(sql=sql_statement, con=self.engine)

    def get_definition_images(self, id_definition: int) -> pd.DataFrame:
        """切り出し定義に紐づいた全ての画像の情報を参照します

        Args:
            id_definition (int): クエリする定義のID

        Returns:
            pd.DataFrame: 結果を格納したデータフレーム
        """
        sql_statement = select(ImageTable).filter(ImageTable.id_definition == id_definition)
        return pd.read_sql_query(sql=sql_statement, con=self.engine)
