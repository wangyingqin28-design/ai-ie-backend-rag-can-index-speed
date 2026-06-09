from typing import Optional
import datetime
import decimal

from sqlalchemy import BigInteger, Boolean, DECIMAL, DateTime, Float, Identity, Index, Integer, PrimaryKeyConstraint, String, Unicode, text
from sqlalchemy.dialects.mssql import TINYINT
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass


class AIBiaoZhunGongXu(Base):
    __tablename__ = 'AI_BiaoZhunGongXu'
    __table_args__ = (
        PrimaryKeyConstraint('bzgxId', name='PK__AI_BiaoZ__B96E5548451D6C5B'),
        {'comment': '标准工序表'}
    )

    bzgxId: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='标准工序ID (雪花算法)')
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


class AICaiPianGongYi(Base):
    __tablename__ = 'AI_CaiPianGongYi'
    __table_args__ = (
        PrimaryKeyConstraint('cpgyId', name='PK__AI_CaiPi__07D8DCB8EC69C516'),
        {'comment': '裁片工艺表'}
    )

    cpgyId: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='工艺记录唯一标识 (雪花算法)')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    gongYiMiaoShu: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='工艺文本描述')
    gongYiWeiZhi: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='位置坐标')
    xbcpId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='关联所属的裁片id')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='归属公司ID')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')
    gongYiLeiXing: Mapped[Optional[int]] = mapped_column(TINYINT, comment='工艺类型（0=工艺/1=备注')


class AICaiZhiLeiXing(Base):
    __tablename__ = 'AI_CaiZhiLeiXing'
    __table_args__ = (
        PrimaryKeyConstraint('czlxId', name='PK__AI_CaiZh__945B4C5674D0863D'),
    )

    czlxId: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    del_flag: Mapped[int] = mapped_column(TINYINT, nullable=False)
    leiXingMingCheng: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'))
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger)
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger)
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger)


class AICaoZuoRiZhi(Base):
    __tablename__ = 'AI_CaoZuoRiZhi'
    __table_args__ = (
        PrimaryKeyConstraint('czrzId', name='PK__AI_CaoZu__B2F703E283DAC736'),
        {'comment': '操作日志表'}
    )

    czrzId: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='操作日志ID (雪花算法)')
    caoZuoZhuJian: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='操作记录的主键')
    caoZuoLeiXing: Mapped[Optional[int]] = mapped_column(TINYINT, comment='操作类型 增删改，1表示修改，2表示删除')
    liShiShuJu: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='历史说明')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    biaoMing: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='表名')


class AIDiQuBianMa(Base):
    __tablename__ = 'AI_DiQuBianMa'
    __table_args__ = (
        PrimaryKeyConstraint('dqbmId', name='PK__AI_DiQuB__4932DDE74B122C91'),
        {'comment': '地区编码表'}
    )

    dqbmId: Mapped[str] = mapped_column(String(6, 'Chinese_PRC_CI_AS'), primary_key=True, comment='地区国标编码')
    diQuMingCheng: Mapped[Optional[str]] = mapped_column(String(50, 'Chinese_PRC_CI_AS'), comment='地区名称')
    fuJiDiquBianMaId: Mapped[Optional[str]] = mapped_column(String(6, 'Chinese_PRC_CI_AS'), comment='父级地区编码')
    diQuCengJi: Mapped[Optional[int]] = mapped_column(TINYINT, comment='地区层级（1 = 省、2 = 市、3 = 区、4 = 街道）')


class AIGongSi(Base):
    __tablename__ = 'AI_GongSi'
    __table_args__ = (
        PrimaryKeyConstraint('gsId', name='PK__AI_GongS__4AF47C7E9D45F957'),
        Index('UQ__AI_GongS__A889DD62BDEEB810', 'gongSiDaiMa', unique=True),
        {'comment': '公司表'}
    )

    gsId: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='公司id (雪花算法)')
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

    gsgjId: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='公司工价ID (雪花算法)')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='公司ID')
    xbgzId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='工种ID')
    gongJia: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 4), comment='工价（元/月）')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')


class AIGongSiYongHu(Base):
    __tablename__ = 'AI_GongSiYongHu'
    __table_args__ = (
        PrimaryKeyConstraint('gsyhId', name='PK__AI_GongS__C355B24EADADF9B0'),
        {'comment': '公司用户表'}
    )

    gsyhId: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='用户唯一标识 (雪花算法)')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    yongHuXingMing: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='用户真实姓名')
    xingBie: Mapped[Optional[int]] = mapped_column(TINYINT, server_default=text('((0))'), comment='性别（0=未知/1=男/2=女）')
    dianHua: Mapped[Optional[str]] = mapped_column(String(11, 'Chinese_PRC_CI_AS'), comment='联系电话（用于登录）')
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

    lsgjId: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='历史工价id (雪花算法)')
    is_gongSi_gongJia: Mapped[Optional[int]] = mapped_column(TINYINT, comment='工价类型：0=区域工价，1=企业工价')
    gjId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='区域工价id或公司工价id')
    gongJia: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 4), comment='变更价格')
    bianGengYuanYin: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='变更原因')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='操作人id')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('(getdate())'), comment='变更时间')


class AIQuYuGongJia(Base):
    __tablename__ = 'AI_QuYuGongJia'
    __table_args__ = (
        PrimaryKeyConstraint('qygjId', name='PK__AI_QuYuG__ACE637D0011B65A6'),
        {'comment': '区域工价表'}
    )

    qygjId: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='工价ID (雪花算法)')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    dqbmId: Mapped[Optional[str]] = mapped_column(String(6, 'Chinese_PRC_CI_AS'), comment='地区编码信息')
    xbgzId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='工种ID')
    gongJia: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 4), comment='工价（元/月）')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')


class AIXiangBaoBaoXing(Base):
    __tablename__ = 'AI_XiangBaoBaoXing'
    __table_args__ = (
        PrimaryKeyConstraint('xbbxId', name='PK__AI_Xiang__3E6A76C16284EE8F'),
        {'comment': '箱包包型表'}
    )

    xbbxId: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='包型唯一ID (雪花算法)')
    baoXingMingCheng: Mapped[str] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), nullable=False, comment='包型名称')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    parent_id: Mapped[Optional[int]] = mapped_column(TINYINT, comment='父级包型ID，0表示一级分类')
    baoXingMiaoShu: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='包型描述')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')
    fubxId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='父包型ID')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger)


class AIXiangBaoBuWei(Base):
    __tablename__ = 'AI_XiangBaoBuWei'
    __table_args__ = (
        PrimaryKeyConstraint('xbbwId', name='PK__AI_Xiang__3E2A64C89A3C7DFC'),
        {'comment': '箱包部位表'}
    )

    xbbwId: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='箱包部位ID (雪花算法)')
    buWeiMingCheng: Mapped[str] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), nullable=False, comment='部位中文名称（通用名）')
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

    xbcpId: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='裁片唯一标识 (雪花算法)')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    caiPianChiCun: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='裁片尺寸（长×宽）')
    xbczId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='裁片材质ID')
    caiPianHouDu: Mapped[Optional[float]] = mapped_column(Float(53), comment='裁片厚度(单位：mm)')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='归属公司ID')
    caiPianMingCheng: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='裁片名称')
    xbbwId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='裁片所属部位ID')
    nanDuXiShu: Mapped[Optional[float]] = mapped_column(Float(53), comment='难度系数')
    xbkhId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='纸格款号款号表id')
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

    xbczId: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='材质ID (雪花算法)')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    caiZhiMingCheng: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='材质标准名称')
    caiZhiLeiXing: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='材质大类')
    caiZhiMiaoShu: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='材质特性描述')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')
    czlxId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='材质类型ID')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger)


class AIXiangBaoGongXu(Base):
    __tablename__ = 'AI_XiangBaoGongXu'
    __table_args__ = (
        PrimaryKeyConstraint('xbgxId', name='PK__AI_Xiang__14F9230788A5A08A'),
        {'comment': '箱包工序表'}
    )

    xbgxId: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='工序ID (雪花算法)')
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


class AIXiangBaoGongZhong(Base):
    __tablename__ = 'AI_XiangBaoGongZhong'
    __table_args__ = (
        PrimaryKeyConstraint('xbgzId', name='PK__AI_Xiang__14790E53FD2CEFF4'),
        {'comment': '箱包工种表'}
    )

    xbgzId: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='工种ID (雪花算法)')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    gongZhongMingCheng: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='工种名称')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='公司ID')


class AIXiangBaoGuiZe(Base):
    __tablename__ = 'AI_XiangBaoGuiZe'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='PK__AI_Xiang__3213E83FE89863E7'),
        {'comment': '箱包规则表（向量化）'}
    )

    id: Mapped[str] = mapped_column(String(50, 'Chinese_PRC_CI_AS'), primary_key=True)
    yongHuId: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='用户id')
    xiangBaoGuiZeLeiXing: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='箱包规则类型')
    xiangBaoGuiZe: Mapped[str] = mapped_column(String(collation='Chinese_PRC_CI_AS'), nullable=False, comment='箱包规则')
    gengXinChaRuId: Mapped[str] = mapped_column(String(24, 'Chinese_PRC_CI_AS'), nullable=False, comment='更新插入id')
    wenDangId: Mapped[str] = mapped_column(String(24, 'Chinese_PRC_CI_AS'), nullable=False, comment='文档id')
    suoYinLeiXing: Mapped[str] = mapped_column(String(50, 'Chinese_PRC_CI_AS'), nullable=False, comment='索引类型')
    suoYinZhuangTai: Mapped[str] = mapped_column(String(50, 'Chinese_PRC_CI_AS'), nullable=False, comment='索引状态')
    banBen: Mapped[int] = mapped_column(Integer, nullable=False, comment='期望的索引版本（每次文档更新时 +1）')
    chuLiDeBanBen: Mapped[int] = mapped_column(Integer, nullable=False, comment='已处理的版本号')
    chuangJianShiJian: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment='创建时间')
    gengXinShiJian: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment='更新时间')
    xiangBaoGuiZeHash: Mapped[str] = mapped_column(String(64, 'Chinese_PRC_CI_AS'), nullable=False, comment='箱包规则哈希值')
    qiYeId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='企业id')
    biaoZhunId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='标准id')
    gengXinYongHuId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='更新用户id')
    cuoWuXinXi: Mapped[Optional[str]] = mapped_column(String(collation='Chinese_PRC_CI_AS'), comment='错误信息')
    xieTiaoShiJian: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='协调时间')
    shanChuShiJian: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')


class AIXiangBaoGuiZeLeiXing(Base):
    __tablename__ = 'AI_XiangBaoGuiZeLeiXing'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='PK__AI_Xiang__3213E83FC695178C'),
        {'comment': '箱包规则类型表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    xiangBaoGuiZeLeiXing: Mapped[str] = mapped_column(String(20, 'Chinese_PRC_CI_AS'), nullable=False, comment='箱包规则类型')
    chuangJianShiJian: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment='创建时间')
    gengXinShiJian: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment='更新时间')
    shanChuShiJian: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')


class AIXiangBaoGuiZee(Base):
    __tablename__ = 'AI_XiangBaoGuiZee'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='PK__AI_Xiang__3213E83FA13643A9'),
        {'comment': '箱包规则表（向量化）'}
    )

    id: Mapped[str] = mapped_column(String(50, 'Chinese_PRC_CI_AS'), primary_key=True)
    yongHuId: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='用户id')
    xiangBaoGuiZeLeiXing: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='箱包规则类型')
    xiangBaoGuiZe: Mapped[str] = mapped_column(String(collation='Chinese_PRC_CI_AS'), nullable=False, comment='箱包规则')
    gengXinChaRuId: Mapped[str] = mapped_column(String(24, 'Chinese_PRC_CI_AS'), nullable=False, comment='更新插入id')
    wenDangId: Mapped[str] = mapped_column(String(24, 'Chinese_PRC_CI_AS'), nullable=False, comment='文档id')
    suoYinLeiXing: Mapped[str] = mapped_column(String(50, 'Chinese_PRC_CI_AS'), nullable=False, comment='索引类型')
    suoYinZhuangTai: Mapped[str] = mapped_column(String(50, 'Chinese_PRC_CI_AS'), nullable=False, comment='索引状态')
    banBen: Mapped[int] = mapped_column(Integer, nullable=False, comment='期望的索引版本（每次文档更新时 +1）')
    chuLiDeBanBen: Mapped[int] = mapped_column(Integer, nullable=False, comment='已处理的版本号')
    chuangJianShiJian: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment='创建时间')
    gengXinShiJian: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment='更新时间')
    xiangBaoGuiZeHash: Mapped[str] = mapped_column(String(64, 'Chinese_PRC_CI_AS'), nullable=False, comment='箱包规则哈希值')
    qiYeId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='企业id')
    biaoZhunId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='标准id')
    gengXinYongHuId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='更新用户id')
    cuoWuXinXi: Mapped[Optional[str]] = mapped_column(String(collation='Chinese_PRC_CI_AS'), comment='错误信息')
    xieTiaoShiJian: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='协调时间')
    shanChuShiJian: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')


class AIXiangBaoKuanHao(Base):
    __tablename__ = 'AI_XiangBaoKuanHao'
    __table_args__ = (
        PrimaryKeyConstraint('xbkhId', name='PK__AI_Xiang__7BCAA94E6EA514D0'),
        {'comment': '箱包款号表'}
    )

    xbkhId: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='箱包型号 (雪花算法)')
    dxfURL: Mapped[str] = mapped_column(String(1000, 'Chinese_PRC_CI_AS'), nullable=False, comment='dxf文件路径')
    laiYuanLeiXing: Mapped[int] = mapped_column(TINYINT, nullable=False, comment='来源类型（从工艺AI智能上传为1，从DXF文件管理器上传为0,后台管理员上传为2）')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    kuanHaoMingCheng: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='产品款式编号')
    banBenHao: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='产品版本号')
    xbbxId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='箱包包型id')
    gsId: Mapped[Optional[int]] = mapped_column(BigInteger, comment='归属企业ID')
    dqbmId: Mapped[Optional[str]] = mapped_column(String(6, 'Chinese_PRC_CI_AS'), comment='地区编码信息')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    in_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='插入人编号')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间')
    up_userid: Mapped[Optional[int]] = mapped_column(BigInteger, comment='最后更新人员')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间')
    beiZhu: Mapped[Optional[str]] = mapped_column(String(1000, 'Chinese_PRC_CI_AS'), comment='备注')


class AILiaotianjilu(Base):
    __tablename__ = 'AI_liaotianjilu'
    __table_args__ = (
        PrimaryKeyConstraint('ltjlid', name='PK_AI_liaotianjilu'),
    )

    ltjlid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64, 'Chinese_PRC_CI_AS'), nullable=False, comment='区分不同聊天记录的唯一键')
    message_role: Mapped[str] = mapped_column(String(10, 'Chinese_PRC_CI_AS'), nullable=False, comment='类别')
    message_content: Mapped[str] = mapped_column(Unicode(collation='Chinese_PRC_CI_AS'), nullable=False, comment='聊天内容')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, comment='是否删除标识，0表示在用，1表示逻辑删除')
    create_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('(getdate())'), comment='插入时间')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='删除时间')
    zh_id: Mapped[Optional[str]] = mapped_column(String(collation='Chinese_PRC_CI_AS'), comment='不同账号的唯一标识')
    xbkh_id: Mapped[Optional[str]] = mapped_column(Unicode(collation='Chinese_PRC_CI_AS'), comment='款号')


class AiBagCategories(Base):
    __tablename__ = 'ai_bag_categories'
    __table_args__ = (
        PrimaryKeyConstraint('category_id', name='PK__ai_bag_c__D54EE9B4CC65C7DF'),
        {'comment': '箱包品类表：\r\n1. 定义包的类型\r\n2. 为不同类型规划所需部件部位。'}
    )

    category_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    category_name: Mapped[str] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), nullable=False)
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'))
    parent_id: Mapped[Optional[int]] = mapped_column(Integer)
    description: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'))
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    in_userid: Mapped[Optional[int]] = mapped_column(Integer)
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    up_userid: Mapped[Optional[int]] = mapped_column(Integer)
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class AiBagModel(Base):
    __tablename__ = 'ai_bag_model'
    __table_args__ = (
        PrimaryKeyConstraint('model_id', name='PK__ai_bag_m__DC39CAF408DA420F'),
        {'comment': '存储DXF解析后的纸格款号数据，关联产品款号与企业，为向量数据库提供基础数据'}
    )

    model_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True, comment='纸格款号唯一标识')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    style_num: Mapped[Optional[str]] = mapped_column(String(50, 'Chinese_PRC_CI_AS'), comment='产品款式编号')
    category_id: Mapped[Optional[int]] = mapped_column(Integer, comment='箱包品类类型（关联子级）')
    enterprise_id: Mapped[Optional[int]] = mapped_column(Integer, comment='归属企业ID')
    encoding: Mapped[Optional[int]] = mapped_column(Integer, comment='地区编码信息')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='当del_flag为1时记录')
    in_userid: Mapped[Optional[int]] = mapped_column(Integer, comment='插入人编号（当有INSERT时记录）')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间（到时分秒）')
    up_userid: Mapped[Optional[int]] = mapped_column(Integer, comment='最后更新人员（当有UPDATE时记录）')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间（到时分秒）')


class AiBagPart(Base):
    __tablename__ = 'ai_bag_part'
    __table_args__ = (
        PrimaryKeyConstraint('bag_part_id', name='PK__ai_bag_p__B1B5EFC2A0C8B660'),
        {'comment': '箱包部位表：定义箱包的标准结构部件及其区域属性，是大模型进行区域间工序拆解的结构锚点。'}
    )

    bag_part_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    part_name_cn: Mapped[str] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), nullable=False)
    part_area: Mapped[str] = mapped_column(String(20, 'Chinese_PRC_CI_AS'), nullable=False)
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'))
    part_name_en: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'))
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    in_userid: Mapped[Optional[int]] = mapped_column(Integer)
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    up_userid: Mapped[Optional[int]] = mapped_column(Integer)
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class AiBagTypePart(Base):
    __tablename__ = 'ai_bag_type_part'
    __table_args__ = (
        PrimaryKeyConstraint('mapping_id', name='PK__ai_bag_t__5AE90045D30A567B'),
        {'comment': '包型-部位关联表：建立箱包类型与箱包部位的关联关系，定义每种箱包类型由哪些标准部位组成。'}
    )

    mapping_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    bag_part_id: Mapped[int] = mapped_column(Integer, nullable=False)
    model_id: Mapped[int] = mapped_column(Integer, nullable=False)
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'))
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    in_userid: Mapped[Optional[int]] = mapped_column(Integer)
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    up_userid: Mapped[Optional[int]] = mapped_column(Integer)
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class AiCutPiece(Base):
    __tablename__ = 'ai_cut_piece'
    __table_args__ = (
        PrimaryKeyConstraint('piece_id', name='PK__ai_cut_p__6E2F332648AB5C12'),
        {'comment': '存储DXF解析后的裁片数据，含尺寸、工艺等，为生产加工提供直接依据'}
    )

    piece_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True, comment='裁片唯一标识')
    layout_cutting: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((1))'), comment='正反开标识（TRUE=是/正开，0=否/反开）')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    piece_size: Mapped[Optional[str]] = mapped_column(String(100, 'Chinese_PRC_CI_AS'), comment='裁片尺寸（长×宽×高）')
    fabric_id: Mapped[Optional[int]] = mapped_column(Integer, comment='裁片材质')
    materithick: Mapped[Optional[float]] = mapped_column(Float(53), comment='裁片厚度(单位：mm)')
    enterprise_id: Mapped[Optional[int]] = mapped_column(Integer, comment='归属企业ID')
    piece_name: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='裁片名称')
    model_id: Mapped[Optional[int]] = mapped_column(Integer, comment='纸格款号款号id（关联的纸格款号款号id）')
    piece_type: Mapped[Optional[int]] = mapped_column(Integer, server_default=text('((0))'), comment='裁片类型（0=料格/1=资料卡/2=正格/3=工艺格/4=其他）')
    img_url: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='裁片图片路径')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='当del_flag为1时记录')
    in_userid: Mapped[Optional[int]] = mapped_column(Integer, comment='插入人编号（当有INSERT时记录）')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间（到时分秒）')
    up_userid: Mapped[Optional[int]] = mapped_column(Integer, comment='最后更新人员（当有UPDATE时记录）')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间（到时分秒）')
    bag_part_id: Mapped[Optional[int]] = mapped_column(Integer, comment='裁片所在部位ID 外键')
    difficulty: Mapped[Optional[float]] = mapped_column(Float(53), comment='难度系数')


class AiEnterprise(Base):
    __tablename__ = 'ai_enterprise'
    __table_args__ = (
        PrimaryKeyConstraint('enterprise_id', name='PK__ai_enter__A541BC65A48CD720'),
        {'comment': '企业信息表\r\n企业ID、全称、地址'}
    )

    enterprise_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    enterprise_name: Mapped[str] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), nullable=False)
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('(NULL)'))
    enterprise_abbr: Mapped[Optional[str]] = mapped_column(String(100, 'Chinese_PRC_CI_AS'))
    enterprise_address: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'))
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('(NULL)'))
    in_userid: Mapped[Optional[int]] = mapped_column(Integer)
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    up_userid: Mapped[Optional[int]] = mapped_column(Integer)
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class AiEnterpriseLaborPrice(Base):
    __tablename__ = 'ai_enterprise_labor_price'
    __table_args__ = (
        PrimaryKeyConstraint('enterprise_labor_price_id', name='PK__ai_enter__CB81F5295D81DEB2'),
        {'comment': '企业工价表：用于支持特定企业自定义的工价标准。业务目的：允许特定箱包生产企业针对某些工种设定自有工价。'}
    )

    enterprise_labor_price_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    enterprise_id: Mapped[int] = mapped_column(Integer, nullable=False)
    work_type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[decimal.Decimal] = mapped_column(DECIMAL(10, 4), nullable=False)
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'))
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    in_userid: Mapped[Optional[int]] = mapped_column(Integer)
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    up_userid: Mapped[Optional[int]] = mapped_column(Integer)
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class AiEnterpriseUser(Base):
    __tablename__ = 'ai_enterprise_user'
    __table_args__ = (
        PrimaryKeyConstraint('user_id', name='PK__ai_enter__B9BE370FB2F961AA'),
        {'comment': '企业用户表：\r\n存储企业用户资料，支撑身份认证、权限分配与操作追溯'}
    )

    user_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    user_name: Mapped[str] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), nullable=False)
    enterprise_id: Mapped[int] = mapped_column(Integer, nullable=False)
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False)
    gender: Mapped[Optional[int]] = mapped_column(Integer, server_default=text("('')"))
    phone_number: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), server_default=text('(NULL)'))
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    in_userid: Mapped[Optional[int]] = mapped_column(Integer)
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    up_userid: Mapped[Optional[int]] = mapped_column(Integer)
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class AiFabrics(Base):
    __tablename__ = 'ai_fabrics'
    __table_args__ = (
        PrimaryKeyConstraint('fabric_id', name='PK__ai_fabri__5BFCADFCCBF3B3C2'),
        {'comment': '材质库表：标准化材质信息，为材质固化推荐工序，推荐缝合设备种类'}
    )

    fabric_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    fabric_name: Mapped[str] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), nullable=False)
    fabric_type: Mapped[str] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), nullable=False)
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'))
    fabric_description: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'))
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    in_userid: Mapped[Optional[int]] = mapped_column(Integer)
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    up_userid: Mapped[Optional[int]] = mapped_column(Integer)
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class AiPieceProcess(Base):
    __tablename__ = 'ai_piece_process'
    __table_args__ = (
        PrimaryKeyConstraint('process_id', name='PK__ai_piece__9446C3E14F0F6891'),
        {'comment': '存储裁片工艺文本及坐标，支撑工艺可视化与生产精准执行'}
    )

    process_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True, comment='工艺记录唯一标识')
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'), comment='是否删除标识，0表示在用，1表示逻辑删除')
    process_name: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='工艺文本描述')
    process_coord: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='位置坐标')
    process_type: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), comment='字段类型')
    piece_id: Mapped[Optional[int]] = mapped_column(Integer, comment='关联所属的裁片id')
    enterprise_id: Mapped[Optional[int]] = mapped_column(Integer, comment='归属企业ID')
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='当del_flag为1时记录')
    in_userid: Mapped[Optional[int]] = mapped_column(Integer, comment='插入人编号（当有INSERT时记录）')
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='插入时间（到时分秒）')
    up_userid: Mapped[Optional[int]] = mapped_column(Integer, comment='最后更新人员（当有UPDATE时记录）')
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='最后更新时间（到时分秒）')


class AiPriceChangeLog(Base):
    __tablename__ = 'ai_price_change_log'
    __table_args__ = (
        PrimaryKeyConstraint('log_id', name='PK__ai_price__9E2397E0E4EB8A8E'),
        {'comment': '工价变更日志表：通过此表可以追踪每次工价调整的具体情况，包括变更前后的价格、变更原因、操作人以及变更时间等详细信息。'}
    )

    log_id: Mapped[int] = mapped_column(BigInteger, Identity(start=1, increment=1), primary_key=True)
    is_enterprise_price: Mapped[bool] = mapped_column(Boolean, nullable=False)
    new_price: Mapped[decimal.Decimal] = mapped_column(DECIMAL(10, 4), nullable=False)
    operator_userid: Mapped[int] = mapped_column(Integer, nullable=False)
    change_time: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text('(getdate())'))
    regional_labor_price_id: Mapped[Optional[int]] = mapped_column(Integer)
    enterprise_labor_price_id: Mapped[Optional[int]] = mapped_column(Integer)
    old_price: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 4))
    change_reason: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'))


class AiProcessStep(Base):
    __tablename__ = 'ai_process_step'
    __table_args__ = (
        PrimaryKeyConstraint('step_id', name='PK__ai_proce__B2E1DE81A427EE9D'),
        {'comment': '工序表：记录具体产品实例的完整工序链，包含材料、部位及父子依赖关系，存储大模型输出的最终结构化结果。'}
    )

    step_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    standard_process_id: Mapped[int] = mapped_column(Integer, nullable=False)
    model_id: Mapped[int] = mapped_column(Integer, nullable=False)
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'))
    technology_exp: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'))
    relevant_part: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'))
    parent_id: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'))
    child_id: Mapped[Optional[int]] = mapped_column(Integer)
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    in_userid: Mapped[Optional[int]] = mapped_column(Integer)
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    up_userid: Mapped[Optional[int]] = mapped_column(Integer)
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class AiRegionalLaborPrice(Base):
    __tablename__ = 'ai_regional_labor_price'
    __table_args__ = (
        PrimaryKeyConstraint('regional_labor_price_id', name='PK__ai_regio__02E613FD5D54B9B5'),
        {'comment': '区域工价表：存储不同地区针对特定工种的劳动力价格标准。业务目的：1. 为箱包生产各工序人工成本核算提供统一、可追溯的工价依据；2. '
                '支持按地理位置动态调整人工成本。'}
    )

    regional_labor_price_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    encoding: Mapped[int] = mapped_column(Integer, nullable=False)
    work_type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[decimal.Decimal] = mapped_column(DECIMAL(10, 4), nullable=False)
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'))
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    in_userid: Mapped[Optional[int]] = mapped_column(Integer)
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    up_userid: Mapped[Optional[int]] = mapped_column(Integer)
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class AiStandardProcess(Base):
    __tablename__ = 'ai_standard_process'
    __table_args__ = (
        PrimaryKeyConstraint('standard_process_id', name='PK__ai_stand__585D33AB95A976D3'),
        {'comment': '标准工序表：记录箱包制作中通用、标准化的工序信息，供系统在解析款图或排产时自动匹配与推荐。'}
    )

    standard_process_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    process_name: Mapped[str] = mapped_column(String(255, 'Chinese_PRC_CI_AS'), nullable=False)
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'))
    description: Mapped[Optional[str]] = mapped_column(String(255, 'Chinese_PRC_CI_AS'))
    work_type_id: Mapped[Optional[int]] = mapped_column(Integer)
    estimated_time_sec: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 4))
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    in_userid: Mapped[Optional[int]] = mapped_column(Integer)
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    up_userid: Mapped[Optional[int]] = mapped_column(Integer)
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class AiWorkType(Base):
    __tablename__ = 'ai_work_type'
    __table_args__ = (
        PrimaryKeyConstraint('work_type_id', name='PK__ai_work___312CCC9DE6B1F135'),
        {'comment': '工种表：存储箱包生产相关工种的基础信息。业务目的：与区域工价表联动，实现“工种+地区”定价。'}
    )

    work_type_id: Mapped[int] = mapped_column(Integer, Identity(start=1, increment=1), primary_key=True)
    work_type_name: Mapped[str] = mapped_column(String(50, 'Chinese_PRC_CI_AS'), nullable=False)
    del_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('((0))'))
    del_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    in_userid: Mapped[Optional[int]] = mapped_column(Integer)
    in_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    up_userid: Mapped[Optional[int]] = mapped_column(Integer)
    up_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
