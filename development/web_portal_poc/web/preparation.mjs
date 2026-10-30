import { createHmac, timingSafeEqual } from 'node:crypto';
import { tokenHash } from './enrollment-client.mjs';
import { bootstrapTemplate, createBootstrapLink } from './bootstrap-link.mjs';
import { createBootstrapEnv } from './bootstrap-artifact.mjs';

const hex=v=>typeof v==='string' && /^[a-f0-9]{64}$/.test(v);
const uuid=v=>typeof v==='string' && /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/.test(v);
const escape=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const preparationText={
  ja:{title:'演習環境の初回準備',account:'自分のAWSアカウント',lab:'演習環境',home:'トップへ戻る',refresh:'進捗を更新',
    steps:['AWSの本人確認','構成の確認','基盤の準備'],confirmAccount:'上の番号が自分のLearner LabのAWSアカウントであることを確認しました（必須）。',begin:'AWSの本人確認へ進む',
    open:'AWSの確認画面を開く（別タブ）',pending:'AWS側での本人確認を待っています。確認用の作成が終わったら、この画面へ戻って進捗を更新してください。',
    helper:'AWSの右上のアカウント番号を確認し、表示された構成を読んでから作成してください。確認と準備に使う処理・進捗保存先を追加します。既存LabRoleの権限を使い、利用料金が発生します。',
    scope:'自動準備するのは5台・接続経路・教材資源などの基盤です。Nginx・DNS・DB・アプリの設定は、この後に自分でサーバーへ入って行います。',
    confirmPlan:'自分の環境の構成と利用資源を確認します（必須）。',plan:'作成する構成を確認する',confirmed:'AWSアカウントの本人確認ができました。',review:'この構成で5台の基盤を作成することを確認しました（必須）。',
    create:'この構成で基盤の準備を開始する',password:'RDP用パスワード（12～128文字・必須）',confirmation:'同じパスワードをもう一度（必須）',
    passwordNote:'踏み台のlabuserで使います。キー配列を確認して入力してください。共有PCには保存せず、会話へ送る必要もありません。',
    resources:'作成する資源',server:'サーバー',type:'種類',disk:'暗号化ディスク合計',zone:'配置先',price:'EC2の概算料金（USD/時間）',otherCosts:'ディスク・公開IPv4・SSM接続口等の料金は別途発生します。',
    roles:{Bastion:'踏み台',Web:'Web',Dns:'DNS',Db:'DB',Package:'教材repo'},
    queued:'準備の要求を受け付けました。進捗を更新して、同じ要求の続きへ進んでください。',building:'サーバーの作成・初期準備を進めています。進捗を更新して状態を確認してください。',observationUnknown:'開始要求の受付状況を確認しています。新しく作り直さず、同じ要求の進捗を更新してください。',passwordInvalid:'パスワードは12～128文字で、確認欄にも同じ値を入力してください。',
    expired:'割当または配布版の期限が過ぎています。先生に更新を確認してください。',planExpired:'構成の確認から時間がたっています。現在の構成を確認し直してください。',
    budget:'既存のサーバーを保持すると、追加5台は現在の配備上限を超えます。既存環境を削除せず、先生に確認してください。',
    denied:'自分の割当・AWS確認・入力を確認できません。登録内容と有効期限を先生に確認してください。',unavailable:'準備の状態を取得できません。Learner Labを確認し、同じ画面で進捗を更新してください。',
    state:'構築の状態'},
  ru:{title:'Первичная подготовка среды',account:'Ваш аккаунт AWS',lab:'Учебная среда',home:'На главную',refresh:'Обновить ход подготовки',
    steps:['Проверка аккаунта AWS','Проверка конфигурации','Подготовка основы'],confirmAccount:'Я проверил(а), что номер выше относится к моему Learner Lab (обязательно).',begin:'Перейти к проверке AWS',
    open:'Открыть проверку AWS (новая вкладка)',pending:'Ожидается проверка в AWS. После создания проверяющих ресурсов вернитесь сюда и обновите состояние.',
    helper:'Проверьте аккаунт справа вверху AWS и состав ресурсов перед созданием. Добавляются обработка проверки и подготовки и хранилище состояния. Используется существующая LabRole; возможна плата за использование.',
    scope:'Автоматически готовится основа: пять серверов, соединения и учебные ресурсы. Nginx, DNS, базу данных и приложение вы настроите самостоятельно внутри серверов.',
    confirmPlan:'Я проверяю конфигурацию и ресурсы своей среды (обязательно).',plan:'Посмотреть создаваемую конфигурацию',confirmed:'Владение аккаунтом AWS подтверждено.',review:'Я подтверждаю создание пяти серверов по этой конфигурации (обязательно).',
    create:'Начать подготовку по этой конфигурации',password:'Пароль RDP (12–128 символов, обязательно)',confirmation:'Повторите пароль (обязательно)',
    passwordNote:'Пароль для labuser на bastion. Проверьте раскладку клавиатуры. Не сохраняйте его на общем ПК и не отправляйте в чат.',
    resources:'Создаваемые ресурсы',server:'Сервер',type:'Тип',disk:'Зашифрованные диски, всего',zone:'Зона',price:'Оценка EC2 (USD/час)',otherCosts:'Диски, публичные IPv4 и точки подключения SSM оплачиваются отдельно.',
    roles:{Bastion:'Bastion',Web:'Web',Dns:'DNS',Db:'БД',Package:'Учебный repo'},
    queued:'Запрос подготовки принят. Обновите состояние, чтобы продолжить тот же запрос.',building:'Идёт создание и начальная подготовка серверов. Обновите состояние.',observationUnknown:'Проверяется приём запроса. Не создавайте среду заново; обновляйте состояние того же запроса.',passwordInvalid:'Введите пароль длиной 12–128 символов и точно повторите его.',
    expired:'Срок назначения или выпуска истёк. Обратитесь к преподавателю.',planExpired:'План устарел. Проверьте текущую конфигурацию ещё раз.',budget:'Существующие серверы сохраняются; ещё пять превысят текущий предел. Не удаляйте среду и обратитесь к преподавателю.',
    denied:'Не удалось подтвердить назначение, AWS или ввод. Уточните назначение и срок у преподавателя.',unavailable:'Не удалось получить состояние подготовки. Проверьте Learner Lab и обновите эту же страницу.',state:'Состояние создания'},
  uz:{title:'Amaliyot muhitini dastlab tayyorlash',account:'O‘z AWS hisobingiz',lab:'Amaliyot muhiti',home:'Bosh sahifaga',refresh:'Jarayonni yangilash',
    steps:['AWS hisobini tekshirish','Konfiguratsiyani tekshirish','Asosni tayyorlash'],confirmAccount:'Yuqoridagi raqam mening Learner Lab AWS hisobim ekanini tekshirdim (majburiy).',begin:'AWS hisobini tekshirishga o‘tish',
    open:'AWS tekshiruvini ochish (yangi varaq)',pending:'AWS tekshiruvi kutilmoqda. Tekshiruv resurslari yaratilgach, bu varaqqa qayting va holatni yangilang.',
    helper:'Yaratishdan oldin AWS oynasining yuqori o‘ngidagi hisob raqamini va resurslar tarkibini tekshiring. Tekshiruv/tayyorlash amallari va holat saqlash joyi qo‘shiladi. Mavjud LabRole ishlatiladi; foydalanish uchun to‘lov bo‘lishi mumkin.',
    scope:'Besh server, ulanishlar va o‘quv resurslaridan iborat asos avtomatik tayyorlanadi. Nginx, DNS, database va app sozlamalarini keyin server ichida o‘zingiz bajarasiz.',
    confirmPlan:'O‘z muhitim konfiguratsiyasi va resurslarini tekshiraman (majburiy).',plan:'Yaratiladigan konfiguratsiyani ko‘rish',confirmed:'AWS hisobi egasi tasdiqlandi.',review:'Ushbu konfiguratsiya bilan beshta server yaratishni tasdiqlayman (majburiy).',
    create:'Ushbu konfiguratsiya bilan tayyorlashni boshlash',password:'RDP paroli (12–128 belgi, majburiy)',confirmation:'Parolni qayta kiriting (majburiy)',
    passwordNote:'Bastiondagi labuser uchun. Keyboard layoutni tekshiring. Umumiy PCda saqlamang va chatga yubormang.',
    resources:'Yaratiladigan resurslar',server:'Server',type:'Turi',disk:'Shifrlangan disklar jami',zone:'Joylashuv zonasi',price:'EC2 taxminiy narxi (USD/soat)',otherCosts:'Disk, ommaviy IPv4 va SSM endpoint uchun alohida to‘lov olinadi.',
    roles:{Bastion:'Bastion',Web:'Web',Dns:'DNS',Db:'DB',Package:'O‘quv repo'},
    queued:'Tayyorlash so‘rovi qabul qilindi. Xuddi shu so‘rovni davom ettirish uchun holatni yangilang.',building:'Serverlar yaratilmoqda va dastlab tayyorlanmoqda. Holatni yangilang.',observationUnknown:'So‘rov qabul qilingani tekshirilmoqda. Qayta yaratmang, shu so‘rov holatini yangilang.',passwordInvalid:'12–128 belgili parolni kiriting va uni bir xil takrorlang.',
    expired:'Biriktirish yoki release muddati tugagan. O‘qituvchidan yangilashni so‘rang.',planExpired:'Reja eskirgan. Joriy konfiguratsiyani qayta tekshiring.',budget:'Mavjud serverlar saqlansa, yana beshta server joriy chegaradan oshadi. Muhitni o‘chirmang, o‘qituvchiga murojaat qiling.',
    denied:'Biriktirish, AWS yoki kiritilgan ma’lumot tasdiqlanmadi. Biriktirish va muddatni o‘qituvchidan tekshiring.',unavailable:'Tayyorlash holatini olib bo‘lmadi. Learner Labni tekshiring va shu sahifada holatni yangilang.',state:'Yaratish holati'},
};

export function preparationToken(config,session,token,{operation,requestId,deploymentId,planDigest=''}) {
  if (!['begin','plan','create','advance','register'].includes(operation) || !hex(session) || !hex(requestId) || !uuid(deploymentId)
      || (operation==='create' && !hex(planDigest))) throw Error('Invalid preparation form');
  return createHmac('sha256',config.secret).update(JSON.stringify(['jdu-portal/prepare/v1',config.origin,
    session,tokenHash(token),operation,requestId,deploymentId,planDigest])).digest('hex');
}
export function checkPreparationToken(config,session,token,context,supplied) {
  try { return hex(supplied) && timingSafeEqual(Buffer.from(preparationToken(config,session,token,context),'hex'),Buffer.from(supplied,'hex')); }
  catch { return false; }
}
export function checkedPreparation(v) {
  if (!v || !['APPROVED','AWS_CONFIRMED','CREATE_REQUESTED'].includes(v.stage) || !uuid(v.deployment_id)
      || !/^[0-9]{12}$/.test(v.account||'') || !/^[a-z0-9][a-z0-9-]{2,31}$/.test(v.lab_id||'')
      || !Number.isSafeInteger(v.deadline) || typeof v.can_continue!=='boolean') throw Error('Invalid preparation');
  if (v.pair_id!==undefined && (v.stage!=='APPROVED' || !hex(v.pair_id) || !Number.isSafeInteger(v.expires_at))) throw Error('Invalid preparation');
  if (v.initial!==undefined) {
    const i=v.initial;
    if (!i || !['NOT_REQUESTED','PLAN_READY','PLAN_EXPIRED','CREATE_REQUESTED','CREATE_OBSERVATION_REQUIRED','STACK_OBSERVED','RESOURCE_BUDGET',
      'SETUP_REQUIRED','SETUP_PENDING','SETUP_OBSERVATION_REQUIRED','REGISTRATION_PENDING','TEACHING_ASSETS_PENDING'].includes(i.stage)) throw Error('Invalid initial state');
    if (['PLAN_READY','PLAN_EXPIRED'].includes(i.stage) && (!hex(i.plan_digest) || i.account!==v.account || i.lab_id!==v.lab_id || i.deployment_id!==v.deployment_id
        || i.root_gib!==96 || i.new_nodes!==5 || !/^us-east-1[a-z]$/.test(i.availability_zone||'')
        || !i.instance_types || Object.keys(i.instance_types).sort().join(',')!=='Bastion,Db,Dns,Package,Web'
        || Object.values(i.instance_types).some(t=>typeof t!=='string' || !/^t[1-9][0-9]*[a-z]*\.(medium|small|micro)$/.test(t))
        || typeof i.compute_hourly_usd!=='string' || !/^\d+(?:\.\d+)?$/.test(i.compute_hourly_usd)
        || !(Number(i.compute_hourly_usd)>0) || !Number.isFinite(Number(i.compute_hourly_usd)))) throw Error('Invalid initial plan');
    if (i.stack_status!==undefined && (typeof i.stack_status!=='string' || !/^[A-Z_]{1,64}$/.test(i.stack_status))) throw Error('Invalid stack state');
    if (['SETUP_REQUIRED','SETUP_PENDING','SETUP_OBSERVATION_REQUIRED','REGISTRATION_PENDING','TEACHING_ASSETS_PENDING'].includes(i.stage)) {
      if (!['check_foundation','close_prepare','close_plan_sent','close_apply_sent','ssh_discover','ssh_init','ssh_enroll','ssh_verify','registration_pending','teaching_assets_pending'].includes(i.setup_phase)
          || typeof i.can_advance!=='boolean'
          || (i.available_after!==undefined && (!Number.isSafeInteger(i.available_after) || i.available_after<0))
          || (i.ssh_completed_roles!==undefined && (!Number.isSafeInteger(i.ssh_completed_roles) || i.ssh_completed_roles<0 || i.ssh_completed_roles>4))
          || (i.setup_result!==undefined && !['ok','pending','unavailable'].includes(i.setup_result))
          || i.lab_ready!==false) throw Error('Invalid setup state');
    }
  }
  return v;
}
export function createPreparationLink(env,v,clock) {
  checkedPreparation(v);
  return createBootstrapLink({...env,PORTAL_BOOTSTRAP_TEMPLATE_URL:env.PORTAL_PREPARATION_TEMPLATE_URL},
    {...v,registered:false},clock);
}
export const preparationTemplate=env=>bootstrapTemplate({...env,PORTAL_BOOTSTRAP_TEMPLATE_URL:env.PORTAL_PREPARATION_TEMPLATE_URL});
export function createPreparationEnv(env=process.env,client,clock) {
  const load=createBootstrapEnv({...env,PORTAL_ENROLLMENT_ENABLED:env.PORTAL_PREPARATION_ENABLED,
    PORTAL_BOOTSTRAP_TEMPLATE_DIGEST:env.PORTAL_PREPARATION_TEMPLATE_DIGEST,
    PORTAL_BOOTSTRAP_TEMPLATE_URL:env.PORTAL_PREPARATION_TEMPLATE_URL},client,clock);
  return async()=>({...env,PORTAL_PREPARATION_TEMPLATE_URL:(await load()).PORTAL_BOOTSTRAP_TEMPLATE_URL});
}
export function preparationHtml(lang,v,{config,session,token,requestId,bootstrapLink}={}) {
  checkedPreparation(v);
  const t=preparationText[lang],initial=v.initial;
  const form=(operation,body='')=>{
    const context={operation,requestId,deploymentId:v.deployment_id,planDigest:operation==='create'?initial.plan_digest:''};
    const csrf=preparationToken(config,session,token,context);
    const confirm=['advance','register'].includes(operation)?'<input type="hidden" name="confirmed" value="yes">':`<label class="confirm"><input type="checkbox" name="confirmed" value="yes" required> ${escape(operation==='begin'?t.confirmAccount:operation==='plan'?t.confirmPlan:t.review)}</label>`;
    return `<form action="/prepare?lang=${lang}" method="post"><input type="hidden" name="operation" value="${operation}"><input type="hidden" name="deployment_id" value="${v.deployment_id}"><input type="hidden" name="request_id" value="${requestId}"><input type="hidden" name="csrf" value="${csrf}">${body}${confirm}<button type="submit">${escape(operation==='advance'?setupText[lang].advance:operation==='register'?registrationText[lang].button:t[operation])}</button></form>`;
  };
  const context=`<dl><dt>${escape(t.account)}</dt><dd>${escape(v.account)}</dd><dt>${escape(t.lab)}</dt><dd>${escape(v.lab_id)}</dd></dl>`;
  let content;
  if (!v.can_continue) content=`<p role="alert">${escape(t.expired)}</p>`;
  else if (v.stage==='APPROVED' && v.pair_id) {
    const link=new URL(bootstrapLink);
    if (link.origin!=='https://us-east-1.console.aws.amazon.com' || link.pathname!=='/cloudformation/home') throw Error('Invalid AWS link');
    content=`<p role="status">${escape(t.pending)}</p><p>${escape(t.helper)}</p><a class="action" href="${escape(link)}" target="_blank" rel="noopener noreferrer">${escape(t.open)}</a>`;
  } else if (v.stage==='APPROVED') content=form('begin');
  else if (v.stage==='AWS_CONFIRMED' || initial?.stage==='NOT_REQUESTED' || initial?.stage==='PLAN_EXPIRED')
    content=`<p role="status">${escape(initial?.stage==='PLAN_EXPIRED'?t.planExpired:t.confirmed)}</p>${form('plan')}`;
  else if (initial?.stage==='RESOURCE_BUDGET') content=`<p role="alert">${escape(t.budget)}</p>${form('plan')}`;
  else if (initial?.stage==='PLAN_READY') {
    const rows=Object.entries(t.roles).map(([r,label])=>`<tr><th scope="row">${escape(label)}</th><td>${escape(initial.instance_types[r])}</td></tr>`).join('');
    content=`<h2>${escape(t.resources)}</h2><div class="table-wrap"><table><thead><tr><th scope="col">${escape(t.server)}</th><th scope="col">${escape(t.type)}</th></tr></thead><tbody>${rows}</tbody></table></div><dl><dt>${escape(t.disk)}</dt><dd>96 GiB</dd><dt>${escape(t.zone)}</dt><dd>${escape(initial.availability_zone)}</dd><dt>${escape(t.price)}</dt><dd>${escape(initial.compute_hourly_usd)}</dd></dl><p>${escape(t.otherCosts)}</p>`;
    const fields=`<input type="hidden" name="plan_digest" value="${initial.plan_digest}"><fieldset><legend>RDP</legend><p id="rdp-password-note">${escape(t.passwordNote)}</p><label for="rdp-password">${escape(t.password)}</label><input id="rdp-password" name="password" type="password" autocomplete="new-password" minlength="12" maxlength="128" required aria-describedby="rdp-password-note"><label for="rdp-confirmation">${escape(t.confirmation)}</label><input id="rdp-confirmation" name="confirmation" type="password" autocomplete="new-password" minlength="12" maxlength="128" required></fieldset>`;
    content+=form('create',fields);
  } else if (initial?.setup_phase) {
    const st=setupText[lang];
    content=`<h2>${escape(st.title)}</h2><p role="status">${escape(st.phases[initial.setup_phase]||registrationText[lang].assetsStage)}</p>`;
    if (initial.ssh_completed_roles!==undefined)content+=`<p>${escape(st.peers)}: ${initial.ssh_completed_roles} / 4</p>`;
    if (initial.stage==='SETUP_OBSERVATION_REQUIRED')content+=`<p role="alert">${escape(st.observation)}</p>`;
    else if (['REGISTRATION_PENDING','TEACHING_ASSETS_PENDING'].includes(initial.stage))content+=v.registration_complete===true
      ?`<p role="status">${escape(registrationText[lang].assetsPending)}</p>`
      :`<p role="status">${escape(st.registration)}</p><p>${escape(registrationText[lang].note)}</p>${form('register')}`;
    else if (initial.can_advance)content+=`${initial.setup_result==='unavailable'?`<p role="alert">${escape(t.unavailable)}</p>`:''}<p>${escape(st.continueNote)}</p>${form('advance')}`;
    else content+=`<p role="alert">${escape(t.unavailable)}</p>`;
  } else content=`<p role="status">${escape(initial?.stage==='CREATE_OBSERVATION_REQUIRED'?t.observationUnknown:initial?t.building:t.queued)}</p>${initial?.stack_status?.endsWith('_FAILED')?`<p role="alert">${escape(t.unavailable)}</p>`:''}`;
  const step=v.stage==='APPROVED'?0:v.stage==='AWS_CONFIRMED'||['NOT_REQUESTED','PLAN_READY','PLAN_EXPIRED','RESOURCE_BUDGET'].includes(initial?.stage)?1:2;
  const progress=`<ol>${t.steps.map((s,k)=>`<li${k===step?' aria-current="step"':''}>${escape(s)}</li>`).join('')}</ol>`;
  return `${progress}<section>${context}<p>${escape(t.scope)}</p>${content}</section><p><a class="action" href="/prepare?lang=${lang}">${escape(t.refresh)}</a></p><a href="/?lang=${lang}">${escape(t.home)}</a>`;
}

const registrationText={
  ja:{button:'自分の環境を採点に登録する',note:'この環境専用の採点用認証を作り、暗号化して自分の踏み台へ設定します。入力やコピーは不要です。',assetsStage:'教材資源の準備待ち',assetsPending:'採点登録が完了しました。教材資源と課題確認の接続は準備中です。'},
  ru:{button:'Зарегистрировать свою среду для оценивания',note:'Учётные данные только для этой среды будут созданы и переданы в зашифрованном виде на ваш bastion. Вводить или копировать их не нужно.',assetsStage:'Ожидается подготовка учебных материалов',assetsPending:'Регистрация для оценивания завершена. Учебные материалы и подключение проверки заданий ещё подготавливаются.'},
  uz:{button:'O‘z muhitimni baholash uchun ro‘yxatdan o‘tkazish',note:'Faqat shu muhit uchun baholash credentiali yaratiladi va shifrlangan holda o‘z bastioningizga o‘rnatiladi. Uni kiritish yoki nusxalash shart emas.',assetsStage:'O‘quv resurslarini tayyorlash kutilmoqda',assetsPending:'Baholash uchun ro‘yxatdan o‘tish tugadi. O‘quv resurslari va vazifalarni tekshirish ulanishi hali tayyorlanmoqda.'},
};

const setupText={
  ja:{title:'作成後の基盤準備',advance:'基盤準備を続ける',peers:'内部SSHの確認済みサーバー',
    continueNote:'同じ5台の準備を続けます。途中で時間がかかった場合も、この画面から続けられます。内部SSHの確認では一時鍵の期限が切れるまで約1分待つ場合があります。',
    observation:'前の処理の完了を確認する必要があります。作り直さず進捗を更新してください。変わらない場合は先生へ連絡してください。',
    registration:'基盤と内部SSHを確認しました。採点登録はまだ完了していません。',
    phases:{check_foundation:'5台の初期状態と通信を確認します。',close_prepare:'教材の取込み完了を確認し、初期取込み用の通信を閉じる準備をします。',close_plan_sent:'初期取込み用の通信だけを閉じる変更内容を確認します。',close_apply_sent:'通信制限の反映と、同じ5台・ディスクが保持されていることを確認します。',ssh_discover:'内部サーバーの接続先を確認します。',ssh_init:'踏み台の中で内部接続用の鍵を準備します。',ssh_enroll:'踏み台から内部4台へのSSH接続を設定します。',ssh_verify:'一時鍵の期限後も内部SSHが使えることを確認します。',registration_pending:'採点登録待ち'}},
  ru:{title:'Подготовка после создания',advance:'Продолжить подготовку основы',peers:'Серверы с проверенным внутренним SSH',
    continueNote:'Продолжается подготовка тех же пяти серверов. Если операция заняла время, продолжайте с этой страницы. Проверка SSH может потребовать около минуты для истечения временного ключа.',
    observation:'Нужно подтвердить завершение предыдущей операции. Обновите состояние, не создавая среду заново. Если состояние не меняется, сообщите преподавателю.',
    registration:'Основа и внутренний SSH проверены. Регистрация для оценивания ещё не завершена.',
    phases:{check_foundation:'Проверка начального состояния и соединений пяти серверов.',close_prepare:'Проверка загрузки материалов и подготовка закрытия доступа для первоначальной загрузки.',close_plan_sent:'Проверка изменений, закрывающих только первоначальную загрузку.',close_apply_sent:'Проверка ограничения доступа и сохранения тех же серверов и дисков.',ssh_discover:'Проверка адресатов внутренних соединений.',ssh_init:'Подготовка ключа внутренних соединений внутри bastion.',ssh_enroll:'Настройка SSH с bastion к четырём внутренним серверам.',ssh_verify:'Проверка SSH после истечения временного ключа.',registration_pending:'Ожидается регистрация для оценивания'}},
  uz:{title:'Yaratilgandan keyingi tayyorlash',advance:'Asosni tayyorlashni davom ettirish',peers:'Ichki SSH tekshirilgan serverlar',
    continueNote:'Xuddi shu besh server tayyorlanadi. Amal vaqt olsa, shu sahifadan davom eting. SSH tekshiruvida vaqtinchalik key muddati tugashi uchun taxminan bir daqiqa kutish mumkin.',
    observation:'Oldingi amal tugaganini tasdiqlash kerak. Muhitni qayta yaratmasdan holatni yangilang. Holat o‘zgarmasa, o‘qituvchiga ayting.',
    registration:'Asos va ichki SSH tekshirildi. Baholash uchun ro‘yxatdan o‘tish hali tugamagan.',
    phases:{check_foundation:'Besh serverning dastlabki holati va ulanishlarini tekshirish.',close_prepare:'Materiallar yuklanganini tekshirish va dastlabki yuklash ulanishini yopishga tayyorlash.',close_plan_sent:'Faqat dastlabki yuklash ulanishini yopadigan o‘zgarishlarni tekshirish.',close_apply_sent:'Ulanish cheklovi hamda o‘sha serverlar va disklar saqlanganini tekshirish.',ssh_discover:'Ichki ulanish manzillarini tekshirish.',ssh_init:'Ichki ulanish keyini bastion ichida tayyorlash.',ssh_enroll:'Bastiondan to‘rtta ichki serverga SSH ulanishini sozlash.',ssh_verify:'Vaqtinchalik key muddati tugagach SSHni tekshirish.',registration_pending:'Baholash uchun ro‘yxatdan o‘tish kutilmoqda'}},
};
