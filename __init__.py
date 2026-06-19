from calibre.customize import InterfaceActionBase


class HL2CalibrePlugin(InterfaceActionBase):
    name = 'hl2calibre'
    actual_plugin = 'calibre_plugins.hl2calibre.action:HL2CalibreAction'
    description = '导入 Moon+ Reader / KOReader 标注到 Calibre'
    supported_platforms = ['windows', 'osx', 'linux']
    version = (1, 0, 1)
    author = 'hl2calibre'
    minimum_calibre_version = (6, 0, 0)
