from bottle import request, response, redirect, static_file
from ..models.schema import User, FormConfig, Submission, Attachment, MailLog, StatusHistory
from .admin_base import render_template, login_required, admin_required
from ..utils.auth import generate_session_token, check_password, hash_password
from ..utils.email import send_email
from ..utils.logger import logger
import json
import datetime
from peewee import fn, JOIN
import os
import config

def setup_admin_routes(app):
    # --- Auth ---
    @app.get('/login')
    def login_page():
        return render_template('login.html')

    @app.post('/login')
    def handle_login():
        username = request.forms.getunicode('username')
        password = request.forms.getunicode('password')
        
        user = None
        try:
            user = User.get(User.username == username)
        except User.DoesNotExist:
            pass

        if user and check_password(password, user.password) and user.is_active:
            token = generate_session_token(user.id)
            response.set_cookie(config.SESSION_NAME, token, max_age=3600*24, path='/', httponly=True)
            logger.info(f"User logged in: {username}")
            # リダイレクトをここから移動
        else:
            logger.warning(f"Login failed for user: {username}")
            return render_template('login.html', error='Invalid username or password')
        
        return redirect('/')

    @app.get('/logout')
    def logout():
        logger.info("User logged out")
        response.delete_cookie(config.SESSION_NAME)
        return redirect('/login')

    # --- Dashboard ---
    @app.get('/')
    @login_required
    def dashboard():
        # 最近の送信
        recent_submissions = Submission.select().order_by(Submission.created_at.desc()).limit(5)
        
        # 統計 (今日、今週、合計)
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0)
        today_count = Submission.select().where(Submission.created_at >= today).count()
        total_count = Submission.select().count()
        
        # フォーム別集計
        form_stats = (FormConfig.select(FormConfig, fn.COUNT(Submission.id).alias('sub_count'))
                     .join(Submission, JOIN.LEFT_OUTER)
                     .group_by(FormConfig)
                     .order_by(fn.COUNT(Submission.id).desc()))

        # 日別データ (Chart.js用)
        # SQLiteでの簡易的な集計
        chart_query = (Submission.select(fn.strftime('%Y-%m-%d', Submission.created_at).alias('date'), fn.COUNT(Submission.id).alias('count'))
                     .where(Submission.created_at >= (datetime.datetime.now() - datetime.timedelta(days=7)))
                     .group_by(fn.strftime('%Y-%m-%d', Submission.created_at))
                     .order_by('date'))
        
        chart_data = [{'date': row.date, 'count': row.count} for row in chart_query]

        return render_template('dashboard.html', 
                               recent_submissions=recent_submissions,
                               today_count=today_count,
                               total_count=total_count,
                               form_stats=form_stats,
                               chart_data=chart_data)

    # --- Submissions ---
    @app.get('/submissions')
    @login_required
    def list_submissions():
        page = int(request.query.decode().get('page', 1))
        per_page = int(request.query.decode().get('per_page', config.PER_PAGE))
        view_mode = request.query.decode().get('view_mode', 'standard')
        form_id = request.query.decode().get('form_id')
        status = request.query.decode().get('status')
        if status is None:
            status = 'exclude_spam'
        q = request.query.getunicode('q')
        
        query = Submission.select().join(FormConfig).where(Submission.is_deleted == False)
        
        if form_id:
            query = query.where(FormConfig.form_id == form_id)
        
        if status:
            if status == 'exclude_spam':
                query = query.where(Submission.status != 'spam')
            else:
                query = query.where(Submission.status == status)
            
        if q:
            query = query.where(Submission.data.contains(q))
            
        total_count = query.count()
        submissions = query.order_by(Submission.created_at.desc()).paginate(page, per_page)
        total_pages = (total_count + per_page - 1) // per_page
        
        forms = FormConfig.select()
        
        return render_template('submissions_list.html', 
                               submissions=submissions, 
                               page=page, 
                               per_page=per_page,
                               view_mode=view_mode,
                               total_pages=total_pages,
                               forms=forms,
                               current_form_id=form_id,
                               current_status=status,
                               q=q)

    @app.post('/submissions/bulk-update')
    @login_required
    def bulk_update_submissions():
        submission_ids = request.forms.getall('submission_ids')
        action = request.forms.getunicode('action')
        
        if not submission_ids:
            return redirect('/submissions?error=No submissions selected')
        
        count = 0
        success_msg = None
        error_msg = None
        try:
            if action == 'delete':
                query = Submission.update(is_deleted=True).where(Submission.id << submission_ids)
                count = query.execute()
            elif action == 'spam':
                query = Submission.update(status='spam', is_spam=True).where(Submission.id << submission_ids)
                count = query.execute()
                # 履歴も追加（オプションだが丁寧）
                for sub_id in submission_ids:
                    StatusHistory.create(
                        submission=sub_id,
                        old_status='unknown',
                        new_status='spam',
                        note='Bulk update to spam',
                        created_by=request.user
                    )
            elif action == 'recheck_spam':
                from ..utils.security import is_spam_content
                for sub_id in submission_ids:
                    try:
                        sub = Submission.get_by_id(sub_id)
                        data = json.loads(sub.data)
                        is_spam, reason = is_spam_content(data, sub.form)
                        
                        new_status = 'spam' if is_spam else 'new'
                        if sub.status != new_status:
                            old_status = sub.status
                            sub.status = new_status
                            sub.is_spam = is_spam
                            sub.save()
                            
                            StatusHistory.create(
                                submission=sub,
                                old_status=old_status,
                                new_status=new_status,
                                note=f'Re-checked spam: {reason}' if is_spam else 'Re-checked: Not spam',
                                created_by=request.user
                            )
                            count += 1
                    except Exception as e:
                        logger.error(f"Error re-checking submission {sub_id}: {e}")
            elif action.startswith('status:'):
                new_status = action.split(':')[1]
                query = Submission.update(status=new_status, is_spam=(new_status == 'spam')).where(Submission.id << submission_ids)
                count = query.execute()
                for sub_id in submission_ids:
                    StatusHistory.create(
                        submission=sub_id,
                        old_status='unknown',
                        new_status=new_status,
                        note='Bulk status update',
                        created_by=request.user
                    )
            
            success_msg = f'Updated {count} submissions'
        except Exception as e:
            logger.error(f"Bulk update failed: {str(e)}")
            error_msg = f'Update failed: {str(e)}'
            
        if success_msg:
            return redirect(f'/submissions?success={success_msg}')
        else:
            return redirect(f'/submissions?error={error_msg}')

    @app.get('/submissions/<id:int>')
    @login_required
    def submission_detail(id):
        sub = None
        try:
            sub = Submission.get_by_id(id)
        except Submission.DoesNotExist:
            return redirect('/submissions')
            
        data = json.loads(sub.data)
        attachments = Attachment.select().where(Attachment.submission == sub)
        mail_logs = MailLog.select().where(MailLog.submission == sub).order_by(MailLog.sent_at.desc())
        history = StatusHistory.select().where(StatusHistory.submission == sub).order_by(StatusHistory.created_at.desc())
        
        return render_template('submission_detail.html', 
                               sub=sub, 
                               data=data, 
                               attachments=attachments,
                               mail_logs=mail_logs,
                               history=history)

    @app.post('/submissions/<id:int>/status')
    @login_required
    def update_status(id):
        redirect_url = f'/submissions/{id}'
        try:
            sub = Submission.get_by_id(id)
            old_status = sub.status
            new_status = request.forms.getunicode('status')
            note = request.forms.getunicode('note')
            notify_change = request.forms.decode().get('notify_change') == 'on'
            
            if old_status != new_status or note:
                sub.status = new_status
                if new_status == 'spam':
                    sub.is_spam = True
                elif old_status == 'spam' and new_status != 'spam':
                    sub.is_spam = False
                sub.save()
                
                StatusHistory.create(
                    submission=sub,
                    old_status=old_status,
                    new_status=new_status,
                    note=note,
                    created_by=request.user
                )
                
                if notify_change:
                    cfg = sub.form
                    subject = f"[Status Update] {cfg.name} - Submission #{sub.id}"
                    body = f"<h2>Status Updated</h2><p>Submission #{sub.id} status changed from <b>{old_status}</b> to <b>{new_status}</b>.</p>"
                    if note:
                        body += f"<p><b>Note:</b><br>{note}</p>"
                    body += f"<p><a href='{config.BASE_URL}/submissions/{sub.id}'>View Details</a></p>"
                    
                    send_email(
                        to_list=cfg.notify_email,
                        subject=subject,
                        body=body,
                        submission=sub
                    )
                
            redirect_url = f'/submissions/{id}?success=Status updated'
        except Submission.DoesNotExist:
            return redirect('/submissions?error=Submission not found')
        except Exception as e:
            return redirect(f'/submissions/{id}?error=Update failed: {str(e)}')
        
        return redirect(redirect_url)

    @app.post('/submissions/<id:int>/resend')
    @login_required
    def resend_email(id):
        redirect_url = f'/submissions/{id}'
        try:
            sub = Submission.get_by_id(id)
            cfg = sub.form
            data = json.loads(sub.data)
            
            attachments = Attachment.select().where(Attachment.submission == sub)
            att_list = []
            for att in attachments:
                att_list.append((att.original_name, os.path.join(config.UPLOAD_DIR, att.filename), att.mime_type))
            
            subject = "[Resend] " + cfg.subject_template.format(form_name=cfg.name, **data)
            
            # 本文 (簡易)
            if cfg.body_template:
                body = cfg.body_template.format(**data)
            else:
                body = f"<h2>Resent Submission from {cfg.name}</h2><ul>"
                for k, v in data.items():
                    body += f"<li><strong>{k}:</strong> {v}</li>"
                body += "</ul>"

            success, error_msg = send_email(
                to_list=cfg.notify_email,
                subject=subject,
                body=body,
                attachments=att_list,
                submission=sub
            )
            if success:
                redirect_url = f'/submissions/{id}?success=Email resent successfully'
            else:
                redirect_url = f'/submissions/{id}?error=Resend failed: {error_msg}'
        except Exception as e:
            return redirect(f'/submissions/{id}?error=Resend error: {str(e)}')
        
        return redirect(redirect_url)

    # --- Form Config ---
    @app.post('/submissions/<id:int>/mark-spam')
    @login_required
    def mark_as_spam(id):
        try:
            sub = Submission.get_by_id(id)
            sub.status = 'spam'
            sub.is_spam = True
            sub.save()
            
            StatusHistory.create(
                submission=sub,
                old_status='unknown',
                new_status='spam',
                note='Marked as spam from list',
                created_by=request.user
            )
            
            return redirect('/submissions?success=Marked as spam')
        except Submission.DoesNotExist:
            return redirect('/submissions?error=Submission not found')

    @app.get('/forms')
    @admin_required
    def list_forms():
        forms = FormConfig.select()
        return render_template('forms_list.html', forms=forms)

    @app.get('/forms/new')
    @admin_required
    def new_form():
        return render_template('form_edit.html', form=None)

    @app.get('/forms/<id:int>/edit')
    @admin_required
    def edit_form(id):
        cfg = FormConfig.get_by_id(id)
        return render_template('form_edit.html', form=cfg)

    @app.post('/forms/save')
    @admin_required
    def save_form():
        id = request.forms.decode().get('id')
        form_id = request.forms.getunicode('form_id')
        name = request.forms.getunicode('name')
        notify_email = request.forms.getunicode('notify_email')
        allowed_domains = request.forms.getunicode('allowed_domains')
        subject_template = request.forms.getunicode('subject_template')
        body_template = request.forms.getunicode('body_template')
        enable_email_notification = request.forms.decode().get('enable_email_notification') == 'on'
        success_url = request.forms.getunicode('success_url')
        cancel_url = request.forms.getunicode('cancel_url')
        require_japanese = request.forms.decode().get('require_japanese') == 'on'
        validation_rules = request.forms.getunicode('validation_rules')
        is_active = request.forms.decode().get('is_active') == 'on'

        data = {
            'form_id': form_id,
            'name': name,
            'notify_email': notify_email,
            'allowed_domains': allowed_domains,
            'subject_template': subject_template,
            'body_template': body_template,
            'enable_email_notification': enable_email_notification,
            'success_url': success_url,
            'cancel_url': cancel_url,
            'require_japanese': require_japanese,
            'validation_rules': validation_rules,
            'is_active': is_active
        }

        redirect_url = '/forms'
        try:
            if id:
                cfg = FormConfig.get_by_id(id)
                for key, val in data.items():
                    setattr(cfg, key, val)
                cfg.save()
                redirect_url = '/forms?success=Configuration updated'
            else:
                FormConfig.create(**data)
                redirect_url = '/forms?success=New form created'
        except Exception as e:
            return redirect(f'/forms?error=Save failed: {str(e)}')
        
        return redirect(redirect_url)

    @app.post('/forms/<id:int>/delete')
    @admin_required
    def delete_form(id):
        redirect_url = '/forms'
        try:
            cfg = FormConfig.get_by_id(id)
            # 関連データの削除 (CASCADE設定していない場合)
            # Attachmentの物理ファイル削除
            subs = Submission.select().where(Submission.form == cfg)
            for sub in subs:
                atts = Attachment.select().where(Attachment.submission == sub)
                for att in atts:
                    path = os.path.join(config.UPLOAD_DIR, att.filename)
                    if os.path.exists(path):
                        os.remove(path)
                    att.delete_instance()
                
                MailLog.delete().where(MailLog.submission == sub).execute()
                StatusHistory.delete().where(StatusHistory.submission == sub).execute()
                sub.delete_instance()
            
            cfg.delete_instance()
            redirect_url = '/forms?success=Form and all related data deleted'
        except FormConfig.DoesNotExist:
            return redirect('/forms?error=Form not found')
        except Exception as e:
            return redirect(f'/forms?error=Delete failed: {str(e)}')
        
        return redirect(redirect_url)

    # --- User Management ---
    @app.get('/users')
    @admin_required
    def list_users():
        users = User.select()
        return render_template('users_list.html', users=users)

    @app.post('/users/add')
    @admin_required
    def add_user():
        username = request.forms.getunicode('username')
        password = request.forms.getunicode('password')
        role = request.forms.decode().get('role')
        
        redirect_url = '/users'
        if username and password:
            try:
                User.create(
                    username=username,
                    password=hash_password(password),
                    role=role
                )
                redirect_url = '/users?success=User added successfully'
            except Exception as e:
                return redirect(f'/users?error=Failed to add user: {str(e)}')
        
        return redirect(redirect_url)

    @app.post('/users/<id:int>/toggle')
    @admin_required
    def toggle_user(id):
        if request.user.id == id:
            return redirect('/users?error=You cannot deactivate yourself')
        
        try:
            u = User.get_by_id(id)
            u.is_active = not u.is_active
            u.save()
            status = "activated" if u.is_active else "deactivated"
            redirect_url = f'/users?success=User {u.username} {status}'
        except Exception as e:
            return redirect(f'/users?error=Operation failed: {str(e)}')
        
        return redirect(redirect_url)

    @app.post('/users/<id:int>/reset_password')
    @admin_required
    def reset_user_password(id):
        new_password = request.forms.getunicode('new_password')
        if not new_password or len(new_password) < 8:
            return redirect('/users?error=Password must be at least 8 characters')

        try:
            u = User.get_by_id(id)
            u.password = hash_password(new_password)
            u.save()
            redirect_url = f'/users?success=Password reset for {u.username}'
        except Exception as e:
            return redirect(f'/users?error=Failed to reset password: {str(e)}')
        
        return redirect(redirect_url)

    @app.get('/change_password')
    @login_required
    def change_password_page():
        return render_template('change_password.html')

    @app.post('/change_password')
    @login_required
    def handle_change_password():
        current_password = request.forms.getunicode('current_password')
        new_password = request.forms.getunicode('new_password')
        confirm_password = request.forms.getunicode('confirm_password')

        user = request.user

        if not check_password(current_password, user.password):
            return render_template('change_password.html', error='Current password is incorrect')

        if new_password != confirm_password:
            return render_template('change_password.html', error='New passwords do not match')

        if len(new_password) < 8:
            return render_template('change_password.html', error='New password must be at least 8 characters')

        try:
            user.password = hash_password(new_password)
            user.save()
            return redirect('/?success=Password updated successfully')
        except Exception as e:
            return render_template('change_password.html', error=f'Failed to update password: {str(e)}')

    @app.get('/uploads/<filename:path>')
    @login_required
    def download_attachment(filename):
        # ファイルの存在確認
        path = os.path.join(config.UPLOAD_DIR, filename)
        if not os.path.exists(path):
            return redirect('/submissions?error=File not found')
        
        # ダウンロード用のレスポンス
        return static_file(filename, root=config.UPLOAD_DIR, download=True)
