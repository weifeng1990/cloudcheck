from flask import Flask, render_template, request, url_for, redirect, flash, json, send_from_directory, session
from flask_sqlalchemy import SQLAlchemy
import sys, os, click
from datetime import datetime
from shell.Check import hostStatusCheck
from shell.Check import Check
from shell import applog


WIN = sys.platform.startswith('win')
if WIN:  # 如果是 Windows 系统，使用三个斜线
    prefix = 'sqlite:///'
else:  # 否则使用四个斜线
    prefix = 'sqlite:////'

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = prefix + os.path.join(app.root_path, 'data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # 关闭对模型修改的监控
app.config['SECRET_KEY'] = 'dev'

# 在扩展类实例化前加载配置
db = SQLAlchemy(app)  # 初始化扩展，传入程序实例 app


class Host(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(15))
    ssh_user = db.Column(db.String(20))
    ssh_passwd = db.Column(db.String(30))
    ssh_port = db.Column(db.Integer)
    http_user = db.Column(db.String(20))
    http_passwd = db.Column(db.String(30))
    http_port = db.Column(db.Integer)
    role = db.Column(db.String(15))

class Record(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    check_time = db.Column(db.DateTime)
    check_content = db.Column(db.Text)
    check_result = db.Column(db.String(20))
    check_doc = db.Column(db.String(30))

@app.cli.command()  # 注册为命令
@click.option('--drop', is_flag=True, help='Create after drop.')  # 设置选项
def initdb(drop):
    """Initialize the database."""
    if drop:  # 判断是否输入了选项
        db.drop_all()
    db.create_all()
    click.echo('Initialized database.')  # 输出提示信息

@app.route('/test')
def test():
    return render_template('test.html')

@app.route('/')
def index():
    hosts = Host.query.all()
    return render_template('index.html', hosts=hosts)

@app.route('/add', methods=['GET', 'POST'])
def add():
    roles = ['cvm', 'cloudos']
    if request.method == 'POST':
        ip = request.form.get('ip')
        ssh_user = request.form.get('ssh_user')
        ssh_passwd = request.form.get('ssh_passwd')
        ssh_port = request.form.get('ssh_port')
        http_user = request.form.get('http_user')
        http_passwd = request.form.get('http_passwd')
        http_port = request.form.get('http_port')
        role = request.form.get('role')
        host = Host(ip=ip, ssh_user=ssh_user, ssh_passwd=ssh_passwd, ssh_port=ssh_port, http_user=http_user,
                    http_passwd=http_passwd, http_port=http_port, role=role)
        db.session.add(host)
        db.session.commit()
        flash('添加成功')
        return redirect(url_for('index'))
    return render_template('add.html', roles=roles)

@app.route('/host/edit/<int:host_id>', methods=['GET', 'POST'])
def edit(host_id):
    host = Host.query.get_or_404(host_id)
    roles = ['cvm', 'cloudos']
    if request.method == 'POST':
        ip = request.form.get('ip')
        ssh_user = request.form.get('ssh_user')
        ssh_passwd = request.form.get('ssh_passwd')
        ssh_port = request.form.get('ssh_port')
        http_user = request.form.get('http_user')
        http_passwd = request.form.get('http_passwd')
        http_port = request.form.get('http_port')
        role = request.form.get('role')
        host.ip = ip
        host.ssh_user = ssh_user
        host.ssh_passwd = ssh_passwd
        host.ssh_port = ssh_port
        host.http_user = http_user
        host.http_passwd = http_passwd
        host.http_port = http_port
        host.role = role
        db.session.commit()
        flash('修改成功')
        return redirect(url_for('index'))
    return render_template('edit.html', host=host, roles=roles)

@app.route('/host/delete/<int:host_id>', methods=['GET', 'POST'])
def delete(host_id):
    host = Host.query.get_or_404(host_id)
    db.session.delete(host)
    db.session.commit()
    flash('删除成功')
    return redirect(url_for('index'))

def record(result):
    time_now = datetime.strptime(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"%Y-%m-%d %H:%M:%S")
    result1 = {'time':time_now, 'content':'cvm;cloudos', 'result':'yes', 'doc':'test.txt'}
    result1['doc'] = result['filename']
    result1['content'] = result['content']
    check_time = result1['time']
    check_content = result1['content']
    check_result = result1['result']
    check_doc = result1['doc']
    record = Record(check_time=check_time, check_content=check_content, check_result=check_result, check_doc=check_doc)
    db.session.add(record)
    db.session.commit()
    return result1

@app.route('/check/delete/<int:record_id>', methods=['GET', 'POST'])
def delete_record(record_id):
    record = Record.query.get_or_404(record_id)
    db.session.delete(record)
    db.session.commit()
    filename = os.getcwd() + '\\check_result\\' + record.check_doc
    if os.path.exists(filename):
        os.remove(filename)
    else:
        print("文件不存在！")
    flash('删除成功')
    return redirect(url_for('checklist'))

@app.route('/check', methods=['GET', 'POST'])
def check():
    file = applog.Applog()
    file.addLog("##################start check#######################")
    check_ids = request.get_json()
    hostinfos = []
    for check_id in check_ids:
        host = Host.query.get_or_404(check_id['host_id'])
        hostinfo = {'id': host.id, 'role': host.role, 'ip': host.ip, 'status': 'OK', 'sshPort': host.ssh_port,
                    'sshUser': host.ssh_user,
                    'sshPassword': host.ssh_passwd, 'httpPort': host.http_port, 'httpUser': host.http_user,
                    'httpPassword': host.http_passwd, 'check_item': check_id['cas_define_check_id']}
        hostinfos.append(hostinfo)
    data = {}
    if not hostinfos:
        data['data'] = "未添加设备"
    else:
        text = hostStatusCheck(hostinfos)
        if text:
            data['data'] = "巡检结果：" + str(text)
        else:
            result = Check(hostinfos)
            record(result)
            data['data'] = "巡检结果：" + "巡检完成"
    file.addLog("##################end check#######################")
    file.closeLofile()
    return json.dumps(data)

@app.route("/checklist", methods=['GET'])
def checklist():
    records = Record.query.order_by(Record.check_time.desc()).all()
    return render_template('record.html', records=records)


@app.route("/download/<int:record_id>", methods=['GET'])
def download_file(record_id):
    # 需要知道2个参数, 第1个参数是本地目录的path, 第2个参数是文件名(带扩展名)
    directory = os.path.join(os.getcwd(), 'check_result')  # 假设在当前目录
    record = Record.query.get_or_404(record_id)
    filename = record.check_doc
    del record
    return send_from_directory(directory, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5001)
