from typing import Optional
import datetime
import decimal
from decimal import Decimal
from sqlalchemy import DECIMAL

from sqlalchemy import BigInteger, Boolean, DECIMAL, DateTime, Float, Index, Integer, PrimaryKeyConstraint, String, \
    text, CheckConstraint
from sqlalchemy.dialects.mssql import TINYINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship



class Base(DeclarativeBase):
    pass


class AIBiaoZhunGongXu(Base):
    __tablename__ = 'AI_BiaoZhunGongXu'
    __table_args__ = (
        PrimaryKeyConstraint('bzgxId', name='PK__AI_BiaoZ__B96E5548451D6C5B'),
        {'comment': '标准工序表'}
    )

    bzgxId: Mapped[int] = mapped_column(BigInteger, primary_key=True,autoincrement=False,comment='标准工序ID (雪花算法)')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    gongXuMingCheng: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='工序名称')
    gongXuMiaoShu: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='工序详细说明')
    xbgzId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='推荐工种ID')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger)
    #关联关系
    xbgz = relationship(
        "AIXiangBaoGongZhong",
        primaryjoin="foreign(AIBiaoZhunGongXu.xbgzId) == AIXiangBaoGongZhong.xbgzId",
        foreign_keys=[xbgzId],
        backref="biaoZhunGongXu_list",
        lazy="joined"
    )


class AICaiPianGongYi(Base):
    __tablename__ = 'AI_CaiPianGongYi'
    __table_args__ = (
        PrimaryKeyConstraint('cpgyId', name='PK__AI_CaiPi__07D8DCB8EC69C516'),
        {'comment': '裁片工艺表'}
    )

    cpgyId: Mapped[int] = mapped_column(BigInteger, primary_key=True,autoincrement=False,comment='工艺记录唯一标识 (雪花算法)')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    gongYiMiaoShu: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='工艺文本描述')
    gongYiWeiZhi: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='位置坐标')
    xbcpId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='关联所属的裁片id')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='归属企业ID')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')
    gongYiLeiXing: Mapped[Optional[int]] = mapped_column(TINYINT, comment='工艺类型（0=工艺/1=备注）')

class AICaoZuoRiZhi(Base):
    __tablename__ = 'AI_CaoZuoRiZhi'
    __table_args__ = (
        PrimaryKeyConstraint('czrzId', name='PK__AI_CaoZu__B2F703E283DAC736'),
        {'comment': '操作日志表'}
    )

    czrzId: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False,comment='操作日志ID (雪花算法)')
    biaoMing:Mapped[str] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), nullable=False, comment='表名')
    caoZuoZhuJian: Mapped[Optional[int]] = mapped_column(BigInteger, comment='操作行数据的主键')
    caoZuoLeiXing: Mapped[Optional[int]] = mapped_column(TINYINT, comment='操作类型 删改，1表示修改，2表示删除')
    liShiShuJu: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='历史数据')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')

class AIGongSi(Base):
    __tablename__ = 'AI_GongSi'
    __table_args__ = (
        PrimaryKeyConstraint('gsId', name='PK__AI_GongS__4AF47C7E9D45F957'),
        Index('UQ__AI_GongS__A889DD62BDEEB810', 'gongSiDaiMa', unique=True),
        {'comment': '公司表'}
    )

    gsId: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False,comment='公司id (雪花算法)')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    gongSiDaiMa: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='公司代码')
    gongSiQuanCheng: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='企业全称')
    gongSiJianCheng: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='企业简称')
    gongSiDiZhi: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='企业地址（用于工价判断）')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')


class AIGongSiGongJia(Base):
    __tablename__ = 'AI_GongSiGongJia'
    __table_args__ = (
        PrimaryKeyConstraint('gsgjId', name='PK__AI_GongS__2CD21EA9D4BDCC3B'),
        {'comment': '公司工价表'}
    )

    gsgjId: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False,comment='公司工价ID (雪花算法)')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='公司ID')
    xbgzId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='工种ID')
    gongJia: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 4),comment='工价（元/月）')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')
    xbgz = relationship(
        "AIXiangBaoGongZhong",
        primaryjoin="foreign(AIGongSiGongJia.xbgzId) == AIXiangBaoGongZhong.xbgzId",
        foreign_keys=[xbgzId],
        backref='GongSiGongJia_list',
        lazy='joined',
    )
    gs = relationship(
        "AIGongSi",
        primaryjoin="foreign(AIGongSiGongJia.gsId) == AIGongSi.gsId",
        foreign_keys=[gsId],
        lazy='joined',
    )


class AIGongSiYongHu(Base):
    __tablename__ = 'AI_GongSiYongHu'
    __table_args__ = (
        PrimaryKeyConstraint('gsyhId', name='PK__AI_GongS__C355B24EADADF9B0'),
        {'comment': '公司用户表'}
    )

    gsyhId: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False,comment='用户唯一标识 (雪花算法)')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    yongHuXingMing: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='用户真实姓名')
    xingBie: Mapped[Optional[int]] = mapped_column(TINYINT, server_default=text('((0))'), comment='性别（0=未知/1=男/2=女）')
    dianHua: Mapped[Optional[str]] = mapped_column(
        String(11, 'Chinese_PRC_CI_AS'),  # 长度改为11
        CheckConstraint(
            "dianHua LIKE REPLICATE('[0-9]', 11)",
            name="ck_dianhua_11_digits"
        ),
        comment='联系电话（用于登录）',
    )
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='所属公司ID')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')
    miMa: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='密码哈希值（bcrypt加密）')


class AILiShiGongJia(Base):
    __tablename__ = 'AI_LiShiGongJia'
    __table_args__ = (
        PrimaryKeyConstraint('lsgjId', name='PK__AI_LiShi__607A82DCCDDCBE21'),
        {'comment': '历史工价表'}
    )

    lsgjId: Mapped[int] = mapped_column(BigInteger, primary_key=True,autoincrement=False, comment='历史工价id (雪花算法)')
    is_gongSi_gongJia: Mapped[Optional[int]] = mapped_column(TINYINT, comment='工价类型：0=区域工价，1=企业工价')
    gjId: Mapped[Optional[int]] = mapped_column(BigInteger,comment='区域工价id或公司工价id')
    gongJia: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 4),comment='变更价格')
    bianGengYuanYin: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='变更原因')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='操作人id')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('(getdate())'), comment='变更时间')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger,comment='公司ID')


class AIQuYuGongJia(Base):
    __tablename__ = 'AI_QuYuGongJia'
    __table_args__ = (
        PrimaryKeyConstraint('qygjId', name='PK__AI_QuYuG__ACE637D0011B65A6'),
        {'comment': '区域工价表'}
    )

    qygjId: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False,comment='工价ID (雪花算法)')
    dqbmId: Mapped[Optional[str]] = mapped_column(String(6, 'Chinese_PRC_CI_AS'), comment='地区编码信息')
    xbgzId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='工种ID')
    gongJia: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 4), comment='工价（元/月）')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')
    xbgz = relationship(
        "AIXiangBaoGongZhong",
        primaryjoin="foreign(AIQuYuGongJia.xbgzId) == AIXiangBaoGongZhong.xbgzId",
        foreign_keys=[xbgzId],
        backref="QuYuGongJia_list",
        lazy="joined"
    )


class AIXiangBaoBaoXing(Base):
    __tablename__ = 'AI_XiangBaoBaoXing'
    __table_args__ = (
        PrimaryKeyConstraint('xbbxId', name='PK__AI_Xiang__3E6A76C16284EE8F'),
        {'comment': '箱包包型表'}
    )

    xbbxId: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False,comment='包型唯一ID (雪花算法)')
    baoXingMingCheng: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='包型名称')
    parent_id: Mapped[Optional[int]] = mapped_column(TINYINT,server_default=text('((0))'), comment='父级包型等级，0表示一级分类')
    fubxId:Mapped[Optional[int]] = mapped_column(BigInteger,server_default=text('((0))'),comment='父级包型ID')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    baoXingMiaoShu: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='包型描述')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger)

class AIXiangBaoBuWei(Base):
    __tablename__ = 'AI_XiangBaoBuWei'
    __table_args__ = (
        PrimaryKeyConstraint('xbbwId', name='PK__AI_Xiang__3E2A64C89A3C7DFC'),
        {'comment': '箱包部位表'}
    )

    xbbwId: Mapped[int] = mapped_column(BigInteger, primary_key=True,autoincrement=False, comment='箱包部位ID (雪花算法)')
    buWeiMingCheng: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'),comment='部位中文名称（通用名）')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger)

class AIXiangBaoCaiPian(Base):
    __tablename__ = 'AI_XiangBaoCaiPian'
    __table_args__ = (
        PrimaryKeyConstraint('xbcpId', name='PK__AI_Xiang__B7051C8D3D21261D'),
        {'comment': '箱包裁片表'}
    )

    xbcpId: Mapped[int] = mapped_column(BigInteger, primary_key=True,autoincrement=False,comment='裁片唯一标识 (雪花算法)')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    caiPianChiCun: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='裁片尺寸（长×宽）')
    xbczId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='裁片材质ID')
    caiPianHouDu: Mapped[Optional[float]] = mapped_column(Float(53), comment='裁片厚度(单位：mm)')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='归属公司ID')
    caiPianMingCheng: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='裁片名称')
    xbbwId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='裁片所属部位ID')
    nanDuXiShu: Mapped[Optional[float]] = mapped_column(Float(53), comment='难度系数')
    xbkhId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='纸格款号款号id')
    caiPianLeiXing: Mapped[Optional[int]] = mapped_column(TINYINT, comment='裁片类型（0=料格/1=资料卡/2=正格/3=工艺格/4=其他）')
    imgURL: Mapped[Optional[str]] = mapped_column(String(500, 'Chinese_PRC_CI_AS'), comment='裁片图片路径')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')


class AIXiangBaoCaiZhi(Base):
    __tablename__ = 'AI_XiangBaoCaiZhi'
    __table_args__ = (
        PrimaryKeyConstraint('xbczId', name='PK__AI_Xiang__BBBD1A54C05210E3'),
        {'comment': '箱包材质表'}
    )

    xbczId: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False,comment='材质ID (雪花算法)')
    caiZhiMingCheng: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'),comment='材质标准名称')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    caiZhiMiaoShu: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='材质特性描述')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')
    czlxId:Mapped[Optional[int]] = mapped_column(BigInteger,comment='材质类型ID')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger)

class AIXiangBaoGongXu(Base):
    __tablename__ = 'AI_XiangBaoGongXu'
    __table_args__ = (
        PrimaryKeyConstraint('xbgxId', name='PK__AI_Xiang__14F9230788A5A08A'),
        {'comment': '箱包工序表'}
    )

    xbgxId: Mapped[int] = mapped_column(BigInteger, primary_key=True,autoincrement=False, comment='工序ID (雪花算法)')
    xbkhId: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='所属箱包型号表ID（关联款号）')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    bzgxId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='标准工序ID')
    gongXuMingCheng: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='工艺名称')
    parent_id: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='表内父工序ID组')
    child_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment='表内子工序ID')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')
    gongJia: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 4), comment='工价')
    xbgzId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='工种id')
    time: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 4), comment='工时')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='公司Id')
    status: Mapped[Optional[int]]=mapped_column(BigInteger,comment='工序状态')


class AIXiangBaoGongZhong(Base):
    __tablename__ = 'AI_XiangBaoGongZhong'
    __table_args__ = (
        PrimaryKeyConstraint('xbgzId', name='PK__AI_Xiang__14790E53FD2CEFF4'),
        {'comment': '箱包工种表'}
    )

    xbgzId: Mapped[int] = mapped_column(BigInteger, primary_key=True,autoincrement=False, comment='工种ID (雪花算法)')
    gongZhongMingCheng:Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'),comment='工种名称')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger)
class AIXiangBaoGuiZe(Base):
    __tablename__ = 'AI_XiangBaoGuiZe'
    __table_args__ = (
        PrimaryKeyConstraint('xbgzId', name='PK__AI_Xiang__14790E53C2F8ADAF'),
        {'comment': '箱包规则表（向量化）'}
    )

    xbgzId: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False,comment='箱包规则ID (雪花算法)')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    gsyhId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='用户id')
    guiZeLeiXing: Mapped[Optional[int]] = mapped_column(TINYINT, comment='规则类型')
    xiangBaoGuiZe: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='箱包规则')
    status: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='数据状态')
    observed_version: Mapped[Optional[int]] = mapped_column(Integer, comment='期望的索引版本（每次文档更新时+1）')
    version: Mapped[Optional[int]] = mapped_column(Integer, comment='已处理的版本号')
    errMsg: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='错误信息')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')


class AIXiangBaoKuanHao(Base):
    __tablename__ = 'AI_XiangBaoKuanHao'
    __table_args__ = (
        PrimaryKeyConstraint('xbkhId', name='PK__AI_Xiang__7BCAA94E6EA514D0'),
        {'comment': '箱包款号表'}
    )

    xbkhId: Mapped[int] = mapped_column(BigInteger, primary_key=True,autoincrement=False,comment='箱包型号 (雪花算法)')
    dxfURL: Mapped[str] = mapped_column(String(1000, 'Chinese_PRC_CI_AS'), nullable=False, comment='dxf文件路径')
    laiYuanLeiXing: Mapped[int] = mapped_column(TINYINT, nullable=False, comment='来源类型（dxf解析为1，单独上传为0）')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    kuanHaoMingCheng: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='产品款式编号')
    banBenHao: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='产品版本号')
    xbbxId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='箱包包型id')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='归属企业ID')
    dqbmId: Mapped[Optional[str]] = mapped_column(String(6, 'Chinese_PRC_CI_AS'), comment='地区代码信息')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')
    beiZhu: Mapped[Optional[str]] = mapped_column(String(1000, 'Chinese_PRC_CI_AS'), comment='备注')

class AIliaotianjilu(Base):
    __tablename__ = 'AI_liaotianjilu'
    __table_args__ = (
     PrimaryKeyConstraint('ltjlid',name='PK__AI_Xiang__7BCAA94E6EA513D0'),
     {'comment':'AI聊天记录表'}
    )

    ltjlId:Mapped[int]=mapped_column('ltjlid',BigInteger,primary_key=True,autoincrement=False,comment='聊天记录Id(雪花算法)')
    sessionId:Mapped[str]=mapped_column('session_id',String(64,'Chinese_PRC_CI_AS'),nullable=False,comment='聊天记录的唯一标识符')
    message_role:Mapped[str]=mapped_column('message_role',String(10,'Chinese_PRC_CI_AS'),nullable=False,comment='角色类型')
    message_content:Mapped[str]=mapped_column('message_content',String(1000,'Chinese_PRC_CI_AS'),nullable=False,comment='聊天记录')
    create_at:Mapped[Optional[datetime.datetime]]=mapped_column('create_at',DateTime,comment='数据生成时间')
    del_time:Mapped[Optional[datetime.datetime]]=mapped_column('del_time',DateTime,comment="数据删除时间")
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    xbkh_id: Mapped[str] = mapped_column('xbkh_id', String(1000, 'Chinese_PRC_CI_AS'), nullable=False,
                                                 comment='箱包款号')
    title: Mapped[str]=mapped_column('title',String(255,'Chinese_PRC_CI_AS'),nullable=False,comment='聊天标题')
    zh_id: Mapped[str]=mapped_column('zh_id',String(1000,'Chinese_PRC_CI_AS'),nullable=False,comment='公司的标识id')



class AIDiQuBianMa(Base):
    __tablename__ = 'AI_DiQuBianMa'
    __table_args__ = (
        PrimaryKeyConstraint('dqbmId', name='PK__AI_DiQuB__4932DDE74B122C91'),
        {'comment': '地区编码表'}
    )

    dqbmId: Mapped[str] = mapped_column(String(6, 'Chinese_PRC_CI_AS'), primary_key=True, comment='地区国标编码')
    diQuCengJi: Mapped[Optional[int]] = mapped_column(TINYINT,comment='地区层级（1 = 省、2 = 市、3 = 区、4 = 街道）')
    diQuMingCheng: Mapped[Optional[str]] = mapped_column(String(50, 'Chinese_PRC_CI_AS'), comment='地区名称')
    fuJiDiquBianMaId: Mapped[Optional[str]] = mapped_column(String(6, 'Chinese_PRC_CI_AS'), comment='父级地区编码')

class AICaiZhiLeiXing(Base):
    __tablename__ = 'AI_CaiZhiLeiXing'
    __table_args__ = (
        PrimaryKeyConstraint('czlxId', name='PK__AI_CaiZh__8E7720D09C0E5B0B'),
    )

    czlxId: Mapped[int] = mapped_column(BigInteger, autoincrement=False,primary_key=True)
    del_flag: Mapped[int] = mapped_column(TINYINT, nullable=False)
    leiXingMingCheng: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'))
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger)
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger)
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger)

class AICaiZhiJiaGe(Base):
        __tablename__ = 'AI_CaiZhiJiaGe'
        __table_args__ = (
            PrimaryKeyConstraint('czjgId', name='PK__czjg__168D620707F7CF94'),
            {'comment': '材质价格表'}
        )

        czjgId: Mapped[int] = mapped_column(BigInteger, primary_key=True,autoincrement=False, comment='材质价格ID')
        gsId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='公司ID')
        czjg: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 4), comment='材质价格')
        in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
        up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='更新时间')
        in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人员ID')
        up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='更新人员ID')
        del_flag: Mapped[Optional[bool]] = mapped_column(Boolean, comment='删除标志')
        xbczId: Mapped[Optional[int]] = mapped_column(BigInteger,comment='箱包材质ID')