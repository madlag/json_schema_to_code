from setuptools import setup


def readme():
    with open('README.md') as f:
        return f.read()

setup(name='json_schema_to_cs',
      version='0.1',
      description='json_schema_to_cs is a python package for ...',
      long_description=readme(),
      classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.0',
        'Topic :: Text Processing',
      ],
      keywords='',
      url='',
      author='',
      author_email='',
      license='MIT',
      packages=['json_schema_to_cs'],
      install_requires=['click', 'jinja2'],
      test_suite='nose.collector',
      tests_require=['nose', 'nose-cover3'],
      entry_points={
          'console_scripts': ['json_schema_to_cs=json_schema_to_cs.json_schema_to_cs:json_schema_to_cs'],
      },
      include_package_data=True,
      zip_safe=False)