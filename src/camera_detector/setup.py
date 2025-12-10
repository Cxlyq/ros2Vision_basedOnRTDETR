from setuptools import find_packages, setup
from glob import glob
import os

package_name = 'camera_detector'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),

    package_data={
        package_name: [
            'weights/*.pth',        # 包含 weights 目录下的模型
            'external_models/**/*', # 递归包含 external_models 下的所有文件(包括yml config)
        ]
    },

    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # 安装 launch 文件
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        # 安装 config 文件
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='cx',
    maintainer_email='cx3348269780@outlook.com',
    description='RT-DETR Perception Node',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            # 格式: '可执行名 = 包名.文件名:main函数'
            'perception_node = camera_detector.perception_node:main',
        ],
    },
)
