from setuptools import setup, find_packages

setup(
    name='django_automate_kit',
    version='1.0.0',
    author='Abel Ayalew',
    author_email='abelayalew81@gmail.com',
    description='A toolkit for automating crud operations for rest and graphql',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/abelayalew/django-automate-kit',
    packages=find_packages(),
    install_requires=[
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)
