import logging
import os
import re
import shutil
import subprocess
import sys
from functools import reduce
from os import path
from time import sleep
from typing import List

import click

# noinspection SpellCheckingInspection
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %I:%M:%S %p',
    level=logging.INFO
)
logger = logging.getLogger()

work_dir = path.dirname(path.abspath(__file__))

with open(path.join(work_dir, 'job_template.sh')) as f:
    template: str = f.read()


def job_template(job_name: str, cpus_per_task: int, input_file: str, output_format: str, output_file: str,
                 log_path: str, babel_cmd: str, babel_options: str) -> str:
    if sys.platform == 'linux':
        quotes = '\''
        delete_cmd = 'rm'
    else:
        quotes = '\"'
        delete_cmd = 'del'

    return reduce(lambda a, b: a.replace(b[0], b[1]), [
        ('${JOB_NAME}', job_name),
        ('${LOG_PATH}', log_path),
        ('${CPUS_PER_TASK}', str(cpus_per_task)),
        ('${INPUT_FILE}', quotes + input_file + quotes),
        ('${OUTPUT_FORMAT}', output_format),
        ('${OUTPUT_FILE}', quotes + output_file + quotes),
        ('${BABEL}', babel_cmd),
        ('${BABEL_OPTIONS}', '' if babel_options is None else babel_options),
        ('${DELETE_CMD}', delete_cmd),
    ], template)


def shell(args: List[str]) -> str:
    cmd = ' '.join(args)
    logger.info(f'command : {cmd}')
    proc = subprocess.Popen(cmd, cwd=os.getcwd(), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate()
    if proc.returncode == 0:
        if out:
            logger.info(out)
    else:
        raise Exception(err)
    return out


def job_summit(job_file: str) -> str:
    # Submitted batch job 13
    stdout: str = shell(['sbatch', job_file])
    return stdout.strip().split()[3].strip()


def job_running() -> List[str]:
    # JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)
    #    90       199 PRosetta     root  R       2:39      1 102-smv4
    stdout: str = shell(['squeue'])
    running_job_ids: List[str] = []
    for line in stdout.split('\n'):
        trimmed = line.strip()
        if re.search('^\s*[0-9]+', trimmed):
            running_job_ids.append(trimmed.split()[0])
    return running_job_ids


def job_wait(job_ids: List[str]):
    def is_running() -> bool:
        running_job_ids: List[str] = job_running()
        for job_id in job_ids:
            if job_id in running_job_ids:
                return True
        else:
            return False

    while is_running():
        logger.info('still working...')
        sleep(10)


# default max_content_width = 80
@click.command(context_settings=dict(max_content_width=110))
@click.option('--src', nargs=1, default=None, type=click.Path(exists=True), required=True,
              help='input molecule file or directory. ex) source.mol2, ./target')
@click.option('--output_format', nargs=1, default=None, type=str, required=True,
              help='output molecule file format. ex) sdf, pdbqt')
@click.option('--dist', nargs=1, default='./dist', type=click.Path(), required=False,
              show_default=True, help='output molecule dist directory.')
@click.option('--babel_cmd', nargs=1, default='obabel', type=click.Choice(['babel', 'obabel']), required=False,
              show_default=True, help='babel command.')
@click.option('--babel_option', nargs=1, default=None, type=str, required=False,
              help='open babel options. ex) --gen3d -p 7.4')
def app(src: str, output_format: str, dist: str = './dist', babel_cmd: str = 'obabel', babel_option: str = None):
    logger.info("************ parameter ************")
    logger.info(f'src : {src}')
    logger.info(f'dist : {dist}')
    logger.info(f'output_format : {output_format}')
    logger.info(f'babel_cmd : {babel_cmd}')
    logger.info(f'babel_option : {babel_option}')
    logger.info("***********************************")

    dist_path: str = path.abspath(path.join(work_dir, dist))
    if path.exists(dist_path):
        shutil.rmtree(dist_path, ignore_errors=True)
    if not path.exists(dist_path):
        logger.info(f'create dist directory : {dist_path}')
        os.mkdir(dist_path)

    source_path: str = path.join(dist_path, 'source')
    if not path.exists(source_path):
        logger.info(f'create source directory : {source_path}')
        os.mkdir(source_path)

    output_path: str = path.join(dist_path, 'output')
    if not path.exists(output_path):
        logger.info(f'create output directory : {output_path}')
        os.mkdir(output_path)

    job_path: str = path.join(dist_path, 'job')
    if not path.exists(job_path):
        logger.info(f'create job directory : {job_path}')
        os.mkdir(job_path)

    log_path: str = path.join(dist_path, 'log')
    if not path.exists(log_path):
        logger.info(f'create log directory : {log_path}')
        os.mkdir(log_path)

    logger.info('molecule split...')
    if path.isfile(src):
        shell([babel_cmd, src, '-m', '-O', path.join(source_path, os.path.basename(src))])
    else:
        src_path = path.abspath(path.join(work_dir, src))
        for f in os.listdir(src_path):
            src_file_path = path.join(src_path, f)
            try:
                if path.isfile(src_file_path):
                    shell([babel_cmd, src_file_path, '-m', '-O', path.join(source_path, f)])
            except Exception as e:
                logging.error(f'babel error : {e}')
                pass

    logger.info('create job script...')
    job_ids: List[str] = []
    for f in os.listdir(source_path):
        file_name_without_extension = os.path.splitext(os.path.basename(f))[0]
        input_file = path.abspath(path.join(source_path, f))
        output_file = path.abspath(path.join(output_path, f'{file_name_without_extension}.{output_format}'))

        script = job_template(f, 1, input_file, output_format, output_file, log_path, babel_cmd, babel_option)

        job_file = path.abspath(path.join(job_path, f'{file_name_without_extension}.sh'))
        with open(job_file, 'w') as jf:
            jf.write(script)

        job_id: str = job_summit(job_file)
        logger.info(f'job id : {job_id}')
        job_ids.append(job_id)

    logger.info(f'result directory : {output_path}')

    job_wait(job_ids)


# python main.py --src test/test.mol2 --output_format sdf --babel_option "--gen3D -p 7.4"
if __name__ == '__main__':
    app()
    # app('test/test.mol2', './', 'sdf', '--gen3D -p 7.4')
