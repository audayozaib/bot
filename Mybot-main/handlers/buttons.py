import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db
import config
from keyboards import (
    get_dev_keyboard, get_admin_keyboard, get_user_keyboard,
    get_back_keyboard, get_categories_keyboard, get_format_keyboard,
    get_time_keyboard, get_files_keyboard, get_categories_keyboard_edit,
    get_format_keyboard_edit
)
from utils import post_job, finalize_channel_addition

logger = logging.getLogger(__name__)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if user_id == config.DEVELOPER_ID: 
        role = "dev"
    elif db.is_admin(user_id): 
        role = "admin"
    else: 
        role = "user"

    # 1. زر تعديل الوقت
    if data == "edit_channel_time":
        await query.edit_message_text("اختر طريقة النشر الجديدة:", reply_markup=get_time_keyboard())
        return

    # 2. إدارة القنوات (تم التعديل ليعمل مع المستخدمين العاديين)
    if data == "manage_channels":
        # ✅ استخدام Context Manager
        with db.get_db_session() as session:
            all_channels = session.query(db.Channel).all()
            
            # قائمة لتخزين القنوات التي يحق للمستخدم إدارتها
            accessible_channels = []

            for ch in all_channels:
                try:
                    # 1. التحقق من أن البوت مشرف
                    bot_member = await context.bot.get_chat_member(ch.channel_id, context.bot.id)
                    if bot_member.status not in ['administrator', 'creator']:
                        continue 

                    # 2. التحقق من أن المستخدم الحالي مشرف في القناة
                    user_member = await context.bot.get_chat_member(ch.channel_id, user_id)
                    if user_member.status in ['administrator', 'creator']:
                        accessible_channels.append(ch)
                        await asyncio.sleep(0.05)
                    
                except Exception as e:
                    logger.warning(f"Skipping channel {ch.channel_id}: {e}")
                    continue
            
            if not accessible_channels:
                await query.edit_message_text(
                    "لا توجد قنوات تملك فيها صلاحيات إدارية (أنت والبوت مشرفين).", 
                    reply_markup=get_back_keyboard(role)
                )
                return
            
            keyboard = []
            for ch in accessible_channels:
                btn_text = f"{ch.title} ({ch.category})"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"edit_channel_{ch.id}")])
            
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"back_{role}")])
            await query.edit_message_text(
                "قوائم القنوات التي تملك فيها صلاحيات:", 
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

    # زر إعدادات القناة (تم السماح للمستخدمين بالدخول طالما مروا من الفلتر)
    if data.startswith("edit_channel_") and data != "edit_channel_time":
        try:
            ch_id = int(data.split("_")[2])
        except ValueError:
            return

        context.user_data['editing_channel_id'] = ch_id
        
        keyboard = [
            [InlineKeyboardButton("🔄 تغيير نوع المحتوى", callback_data="change_cat_select")],
            [InlineKeyboardButton("🎨 تغيير شكل الرسالة", callback_data="change_fmt_select")],
            [InlineKeyboardButton("⏰ تغيير الوقت", callback_data="edit_channel_time")],
            [InlineKeyboardButton("⭐ تعيين ملصق تفاعلي", callback_data="set_sticker_flow")],
            [InlineKeyboardButton("🗑️ حذف القناة", callback_data="confirm_del_channel")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="manage_channels")]
        ]
        await query.edit_message_text("خيارات القناة:", reply_markup=InlineKeyboardMarkup(keyboard))

    # --- إعداد الملصق التفاعلي ---
    if data == "set_sticker_flow":
        ch_id = context.user_data.get('editing_channel_id')
        if not ch_id: 
            return
        context.user_data['action'] = 'waiting_sticker'
        await query.edit_message_text(
            "✏️ أرسل الملصق (Sticker) الذي تريده أن ينشر تلقائياً:", 
            reply_markup=get_back_keyboard(role)
        )

    # حذف القناة
    if data == "confirm_del_channel":
        ch_id = context.user_data.get('editing_channel_id')
        if not ch_id: 
            return
        
        keyboard = [
            [InlineKeyboardButton("❌ لا، ارجع", callback_data=f"edit_channel_{ch_id}")],
            [InlineKeyboardButton("✅ نعم، احذف القناة", callback_data=f"delete_channel_{ch_id}")]
        ]
        await query.edit_message_text(
            "⚠️ هل أنت متأكد من حذف هذه القناة من النظام؟", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    if data.startswith("delete_channel_"):
        ch_id = int(data.split("_")[2])
        
        # ✅ استخدام Context Manager
        with db.get_db_session() as session:
            ch = session.query(db.Channel).filter_by(id=ch_id).first()
            if ch:
                title = ch.title
                session.delete(ch)
                msg = f"✅ تم حذف القناة <b>{title}</b> بنجاح."
            else:
                msg = "❌ لم يتم العثور على القناة."
        
        context.user_data['editing_channel_id'] = None
        await query.edit_message_text(msg, parse_mode='HTML', reply_markup=get_back_keyboard(role))

    # تغيير الفئة والتنسيق
    if data == "change_cat_select":
        await query.edit_message_text(
            "اختر نوع المحتوى الجديد:", 
            reply_markup=get_categories_keyboard_edit(context)
        )

    if data == "change_fmt_select":
        await query.edit_message_text(
            "اختر شكل الرسالة الجديد:", 
            reply_markup=get_format_keyboard_edit(context)
        )

    if data.startswith("set_edit_cat_"):
        new_cat = data.split("_")[3]
        ch_id = context.user_data.get('editing_channel_id')
        if ch_id:
            # ✅ استخدام Context Manager
            with db.get_db_session() as session:
                try:
                    ch = session.query(db.Channel).filter_by(id=ch_id).first()
                    if ch:
                        ch.category = new_cat
                        msg = f"✅ تم تغيير نوع المحتوى إلى <b>{new_cat}</b>."
                    else:
                        msg = "❌ حدث خطأ."
                except Exception as e:
                    logger.error(f"Error updating category: {e}")
                    msg = "❌ حدث خطأ في قاعدة البيانات."
            
            await query.edit_message_text(msg, parse_mode='HTML', reply_markup=get_back_keyboard(role))

    if data.startswith("set_edit_fmt_"):
        new_fmt = data.split("_")[3]
        ch_id = context.user_data.get('editing_channel_id')
        if ch_id:
            # ✅ استخدام Context Manager
            with db.get_db_session() as session:
                try:
                    ch = session.query(db.Channel).filter_by(id=ch_id).first()
                    if ch:
                        ch.msg_format = new_fmt
                        msg = f"✅ تم تغيير شكل الرسالة إلى <b>{new_fmt}</b>."
                    else:
                        msg = "❌ حدث خطأ."
                except Exception as e:
                    logger.error(f"Error updating format: {e}")
                    msg = "❌ حدث خطأ في قاعدة البيانات."
            
            await query.edit_message_text(msg, parse_mode='HTML', reply_markup=get_back_keyboard(role))

    # إدارة المشرفين
    if data == "manage_admins":
        if user_id != config.DEVELOPER_ID:
            await query.edit_message_text(
                "⛔️ هذا القسم للمطور فقط.", 
                reply_markup=get_back_keyboard(role)
            )
            return
        keyboard = [
            [InlineKeyboardButton("➕ إضافة مشرف", callback_data="add_admin_step1")],
            [InlineKeyboardButton("➖ حذف مشرف", callback_data="del_admin_step1")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_dev")]
        ]
        await query.edit_message_text("اختر العملية:", reply_markup=InlineKeyboardMarkup(keyboard))

    if data == "add_admin_step1":
        context.user_data['action'] = 'add_admin'
        await query.edit_message_text(
            "أرسل الآن (آيدي) أو (معرف المستخدم) للإضافة:", 
            reply_markup=get_back_keyboard(role)
        )

    if data == "del_admin_step1":
        context.user_data['action'] = 'del_admin'
        await query.edit_message_text(
            "أرسل الآن (آيدي) أو (معرف المستخدم) للحذف:", 
            reply_markup=get_back_keyboard(role)
        )

    # إدارة الملفات
    if data == "manage_files":
        if not db.is_admin(user_id) and user_id != config.DEVELOPER_ID:
            await query.edit_message_text(
                "⛔️ هذا القسم للمشرفين فقط.", 
                reply_markup=get_back_keyboard(role)
            )
            return 
        await query.edit_message_text(
            "اختر القسم لرفع ملفات الاقتباسات (txt):", 
            reply_markup=get_files_keyboard()
        )

    if data.startswith("upload_"):
        category = data.split("_")[1]
        context.user_data['upload_category'] = category
        msg = f"تم اختيار قسم: <b>{category}</b>\n\nالآن قم بإرسال ملف <code>.txt</code> يحتوي على الاقتباسات."
        await query.edit_message_text(msg, parse_mode='HTML', reply_markup=get_back_keyboard(role))

    # إضافة قناة
    if data == "add_channel_prompt":
        context.user_data['step'] = 'waiting_channel'
        await query.edit_message_text(
            "✏️ قم بإرسال معرف القناة (مثلاً @ChannelName) أو قم بتحويل رسالة (Forward) من القناة هنا:", 
            reply_markup=get_back_keyboard(role)
        )

    # اختيارات القسم والتنسيق والوقت
    if data.startswith("cat_"):
        category = data.split("_")[1]
        context.user_data['selected_category'] = category
        msg = f"تم اختيار القسم: <b>{category}</b>.\n\nاختر شكل الرسالة:"
        await query.edit_message_text(msg, parse_mode='HTML', reply_markup=get_format_keyboard())

    if data.startswith("fmt_"):
        fmt = data.split("_")[1]
        context.user_data['selected_format'] = fmt
        await query.edit_message_text("اختر طريقة النشر:", reply_markup=get_time_keyboard())

    if data.startswith("time_"):
        time_type = data.split("_")[1]
        context.user_data['time_type'] = time_type
        
        is_edit_mode = context.user_data.get('editing_channel_id') is not None
        
        if is_edit_mode:
            # ✅ استخدام Context Manager
            with db.get_db_session() as session:
                ch_id = context.user_data.get('editing_channel_id')
                ch = session.query(db.Channel).filter_by(id=ch_id).first()
                
                msg = ""
                if ch:
                    ch.time_type = time_type
                    if time_type == "default":
                        ch.time_value = None
                        msg = "✅ تم تغيير الوقت إلى <b>افتراضي (عشوائي/فوري)</b>."
                        await query.edit_message_text(msg, parse_mode='HTML', reply_markup=get_back_keyboard(role))
                        return
                    else:
                        if time_type == "fixed":
                            context.user_data['action'] = 'set_fixed_time'
                            msg = f"الوقت الحالي: {ch.time_value}\n\nأرسل الساعات الجديدة (مثلاً: 10, 14, 20):"
                        elif time_type == "interval":
                            context.user_data['action'] = 'set_interval'
                            msg = f"الوقت الحالي: {ch.time_value}\n\nأرسل الفارق الزمني الجديد بالدقائق (مثلاً: 60):"
                        
                        context.user_data['mode'] = 'edit' 
                        await query.edit_message_text(msg, reply_markup=get_back_keyboard(role))
                        return
                else:
                    msg = "❌ القناة غير موجودة."
                    await query.edit_message_text(msg)
                    return

        else:
            msg = ""
            if time_type == "fixed":
                context.user_data['action'] = 'set_fixed_time'
                msg = "أرسل الساعات المطلوبة (مثلاً: 10, 14, 20) مفصولة بفاصلة:"
            elif time_type == "interval":
                context.user_data['action'] = 'set_interval'
                msg = "أرسل الفارق الزمني بالدقائق (مثلاً: 60):"
            else:
                await finalize_channel_addition(update, context, query, role)
                return
            
            await query.edit_message_text(msg, reply_markup=get_back_keyboard(role))
        
    # إحصائيات
    if data == "show_stats":
        stats = db.get_stats()
        await query.edit_message_text(stats, parse_mode='HTML', reply_markup=get_back_keyboard(role))

    # أزرار الرجوع
    if data == "back_home":
        context.user_data.clear()
        kb = get_dev_keyboard() if role == "dev" else (get_admin_keyboard() if role == "admin" else get_user_keyboard())
        title = "لوحة المطور:" if role == "dev" else ("لوحة المشرف:" if role == "admin" else "القائمة الرئيسية:")
        await query.edit_message_text(title, reply_markup=kb)
    
    if data == "back_dev":
        context.user_data.clear()
        await query.edit_message_text("لوحة المطور:", reply_markup=get_dev_keyboard())
    
    if data == "back_admin":
        context.user_data.clear()
        await query.edit_message_text("لوحة المشرف:", reply_markup=get_admin_keyboard())

    if data == "back_user":
        context.user_data.clear()
        await query.edit_message_text("القائمة الرئيسية:", reply_markup=get_user_keyboard())

    # النشر التلقائي
    if data == "toggle_posting":
        # ✅ استخدام Context Manager
        with db.get_db_session() as session:
            setting = session.query(db.BotSettings).filter_by(key='posting_status').first()
            status = setting.value if setting else 'off'
            new_status = 'on' if status == 'off' else 'off'
            
            if setting:
                setting.value = new_status
            else:
                session.add(db.BotSettings(key='posting_status', value=new_status))
        
        state_text = "🟢 مفعل" if new_status == 'on' else "🔴 متوقف"
        msg = f"تم تغيير حالة النشر إلى: <b>{state_text}</b>"
        await query.edit_message_text(msg, parse_mode='HTML', reply_markup=get_back_keyboard(role))

    if data == "post_now":
        await query.edit_message_text("جاري بدء النشر الفوري...")
        await post_job(context, force_one=True)
        msg = "تم النشر الفوري بنجاح ✅"
        await query.edit_message_text(msg, parse_mode='HTML', reply_markup=get_back_keyboard(role))

    # إرسال إذاعة (تم إصلاحه)
    if data == "broadcast_menu":
        if not db.is_admin(user_id) and user_id != config.DEVELOPER_ID:
            await query.edit_message_text(
                "⛔️ هذه الميزة للمشرفين فقط.", 
                reply_markup=get_back_keyboard(role)
            )
            return
        context.user_data['action'] = 'waiting_broadcast'
        await query.edit_message_text(
            "✏️ أرسل الرسالة التي تريد إذاعتها للخاص والقنوات:", 
            reply_markup=get_back_keyboard(role)
        )