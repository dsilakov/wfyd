__version__ = '1.9'

import os
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
    HAVE_SETUPTOOLS = False
else:
    HAVE_SETUPTOOLS = True

README = open('README.txt').read()
CHANGES = open('CHANGES.txt').read()

DATA_FILES = ['wfyd.glade',
              'wfyd.gladep',
              'resources/wfyd-32x32.png',
              'resources/record.png',
              'resources/smallgears.gif',
              'resources/stop.png',
              'doc/wfyd.xml',
             ]

# Make stupid 'sdist' work.
manifested = []
for file in DATA_FILES:
    manifested.append('include %s' % (file,))
manifested.append('')
open('MANIFEST.in', 'w').write('\n'.join(manifested))

# Make stupid 'bdist' work.
bdist_files = {}
for data_file in DATA_FILES:
    path, file = os.path.split(data_file)
    bdist_files.setdefault(path, []).append(data_file)

DISTUTILS_METADATA = {
    'name': 'wfyd',
    'version': __version__,
    'description': 'Minimal time tracker with nag capabilities',
    'long_description': '%s\n\n%s' % (README, CHANGES),
    'author': 'Chris McDonough',
    'author_email': 'chrism@plope.com',
    'maintainer': 'Denis Silakov',
    'maintainer_email': 'd_uragan@rambler.ru',
    'url': 'http://wfyd.sourceforge.net',
    'py_modules': ['wfyd'],
    'data_files': bdist_files.items(),
    'classifiers': [
        'Development Status :: 5 - Production/Stable',
        'Environment :: X11 Applications :: Gnome     ',
        'License :: OSI Approved :: Zope Public License',
        'Programming Language :: Python',
        'Topic :: Office/Business :: Scheduling',
    ]
}

SETUPTOOLS_METADATA = {
    'zip_safe': False,
    'include_package_data': True,
    'install_requires': ['PyGTK',
                         'gnome-python',
                         'sqlite3',
                        ],
    'entry_points': {
        'console_scripts': [
            'wfyd = wfyd:main',
        ],
        'setuptools.installation': [
            'eggsecutable = wfyd:main',
        ]
    }
}

meta = DISTUTILS_METADATA.copy()

if HAVE_SETUPTOOLS:
    meta.update(SETUPTOOLS_METADATA)

setup(**meta)
