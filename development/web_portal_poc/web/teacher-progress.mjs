import { LambdaClient, InvokeCommand } from '@aws-sdk/client-lambda';

const escape=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labId=v=>typeof v==='string' && /^[a-z0-9][a-z0-9-]{2,31}$/.test(v);
export const teacherText={
  ja:{title:'教師用の進捗',course:'授業用',verification:'検証用',lab:'学生Lab',total:'保存済み素点',unknown:'未確認の課題',latest:'最終提出',none:'記録なし',ok:'なし',unavailable:'取得できません',denied:'教師用の閲覧許可がありません。',error:'進捗を取得できません。教師Labの状態を確認してください。',empty:'この区分に担当Labはありません。',next:'次のページ',back:'一覧へ戻る',home:'トップへ',note:'保存済み点数を表示します。未確認の結果で確定済み点数を下げず、未提出と取得失敗を区別します。サーバーは操作しません。'},
  ru:{title:'Прогресс для преподавателя',course:'Учебные Lab',verification:'Тестовые Lab',lab:'Lab студента',total:'Сохранённые баллы',unknown:'Непроверенные задания',latest:'Последняя отправка',none:'Нет записи',ok:'Нет',unavailable:'Недоступно',denied:'Нет разрешения преподавателя на просмотр.',error:'Не удалось получить прогресс. Проверьте Lab преподавателя.',empty:'В этой категории нет назначенных Lab.',next:'Следующая страница',back:'К списку',home:'На главную',note:'Показаны сохранённые баллы. Непроверенный результат не снижает прежнюю оценку. Отсутствие отправки отличается от ошибки чтения. Серверы не изменяются.'},
  uz:{title:'O‘qituvchi uchun natijalar',course:'Dars Lablari',verification:'Sinov Lablari',lab:'Talaba Labi',total:'Saqlangan ball',unknown:'Tekshirilmagan vazifalar',latest:'Oxirgi yuborish',none:'Yozuv yo‘q',ok:'Yo‘q',unavailable:'Olib bo‘lmadi',denied:'O‘qituvchi sifatida ko‘rish ruxsati yo‘q.',error:'Natijalarni olib bo‘lmadi. O‘qituvchi Lab holatini tekshiring.',empty:'Bu bo‘limda biriktirilgan Lab yo‘q.',next:'Keyingi sahifa',back:'Ro‘yxatga qaytish',home:'Bosh sahifa',note:'Saqlangan ball ko‘rsatiladi. Tekshirilmagan natija avvalgi bahoni pasaytirmaydi. Yuborilmagan natija va olish xatosi farqlanadi. Serverlar o‘zgartirilmaydi.'},
};
export function validTeacherEvent(v) {
  if(!v || typeof v.subject!=='string' || !/^[0-9]{1,128}$/.test(v.subject) || typeof v.email!=='string' || !/^[^@\s]{1,64}@jdu\.uz$/i.test(v.email))return false;
  const fields=['subject','email','operation'];
  if(v.operation==='teacher_list')fields.push('context','after');
  else if(v.operation==='teacher_detail')fields.push('lab_id');
  else if(v.operation!=='teacher_access')return false;
  return Object.keys(v).sort().join(',')===fields.sort().join(',') &&
    (v.operation!=='teacher_list' || (['course','verification'].includes(v.context) && (v.after==='' || labId(v.after)))) &&
    (v.operation!=='teacher_detail' || labId(v.lab_id));
}
export function createTeacherClient(env=process.env,client=new LambdaClient({region:'us-east-1'})) {
  const arn=env.GRADE_READER_FUNCTION_ARN,account=env.PORTAL_AWS_ACCOUNT_ID;
  if(!/^[0-9]{12}$/.test(account||'') || !new RegExp(`^arn:aws:lambda:us-east-1:${account}:function:[A-Za-z0-9_-]+$`).test(arn||''))throw Error('Invalid teacher reader');
  return async event=>{
    if(!validTeacherEvent(event))throw Error('Invalid teacher request');
    const result=await client.send(new InvokeCommand({FunctionName:arn,InvocationType:'RequestResponse',Payload:Buffer.from(JSON.stringify(event))}),{abortSignal:AbortSignal.timeout(18000)});
    if(result.FunctionError || result.StatusCode!==200 || !result.Payload || result.Payload.length>65536)throw Error('Teacher progress unavailable');
    const value=JSON.parse(Buffer.from(result.Payload).toString('utf8'));
    if(!['ok','unauthorized','unavailable'].includes(value?.status))throw Error('Teacher progress unavailable');
    return value;
  };
}
export function checkedTeacher(value,{detail=false,context,after='' }={}) {
  if(!value || typeof value.class_id!=='string' || !/^[0-9]{1,12}$/.test(value.class_id))throw Error('Invalid class');
  const rows=detail?[value.student]:value.students;
  if(!Array.isArray(rows) || rows.length>10 || (!detail && value.context!==context))throw Error('Invalid progress');
  const ids=new Set();
  for(const row of rows) {
    if(!row || !labId(row.lab_id) || ids.has(row.lab_id) || !['course','verification'].includes(row.context) || (!detail && (row.context!==context || row.lab_id<=after)) || !['ok','unavailable'].includes(row.status))throw Error('Invalid student progress');
    ids.add(row.lab_id);
  }
  if(!detail && (value.next_after!==null && (!rows.length || value.next_after!==rows.at(-1).lab_id)))throw Error('Invalid next page');
  return value;
}
export function teacherListHtml(lang,value,{validateGrade,maxima}) {
  const t=teacherText[lang],missions=Object.keys(maxima),context=value.context;
  const stamp=v=>typeof v==='string' && v.length<=40 && Number.isFinite(Date.parse(v))?new Date(v).toISOString().slice(0,16).replace('T',' ')+' UTC':t.none;
  const rows=value.students.map(row=>{
    const name=`<th scope="row">${escape(row.lab_id)}</th>`;
    if(row.status!=='ok')return `<tr>${name}<td colspan="${missions.length+3}">${escape(t.unavailable)}</td></tr>`;
    const grade=validateGrade(row.grade);
    const cells=missions.map(m=>{
      const saved=grade.selected[m];
      if (!saved) return `<td><span aria-label="${escape(t.none)}">—</span></td>`;
      return `<td class="${saved.raw_earned===maxima[m]?'score-full':'score-partial'}">${saved.raw_earned} / ${maxima[m]}</td>`;
    }).join('');
    const dates=[...Object.values(grade.current||{}),...Object.values(grade.selected)].map(r=>r?.received_at).filter(v=>typeof v==='string' && Number.isFinite(Date.parse(v)));
    const latest=dates.sort((a,b)=>Date.parse(a)-Date.parse(b)).at(-1);
    return `<tr>${name}${cells}<td>${Object.keys(grade.selected).length?`${grade.raw_earned} / ${grade.raw_maximum}`:escape(t.none)}</td><td>${escape(grade.current_unresolved.length?grade.current_unresolved.join(', '):t.ok)}</td><td>${escape(stamp(latest))}</td></tr>`;
  }).join('');
  const tabs=`<div class="page-toolbar">${['course','verification'].map(key=>`<a class="action" href="/teacher?lang=${lang}&amp;context=${key}"${key===context?' aria-current="page"':''}>${escape(t[key])}</a>`).join('')}<a class="action" href="/checks?lang=${lang}">${{ja:'学生用の課題',ru:'Задания студента',uz:'Talaba vazifalari'}[lang]}</a><form action="/auth/logout" method="post"><button type="submit">${{ja:'ログアウト',ru:'Выйти',uz:'Chiqish'}[lang]}</button></form></div>`;
  const table=rows?`<div class="table-wrap teacher-table" tabindex="0" role="region" aria-labelledby="teacher-caption"><table><caption id="teacher-caption">Class ${escape(value.class_id)} — ${escape(t[context])}</caption><thead><tr><th scope="col">${escape(t.lab)}</th>${missions.map(m=>`<th scope="col">${m}</th>`).join('')}<th scope="col">${escape(t.total)}</th><th scope="col">${escape(t.unknown)}</th><th scope="col">${escape(t.latest)}</th></tr></thead><tbody>${rows}</tbody></table></div>`:`<p>${escape(t.empty)}</p>`;
  const next=value.next_after?`<p><a href="/teacher?lang=${lang}&amp;context=${context}&amp;after=${value.next_after}">${escape(t.next)}</a></p>`:'';
  return tabs+table+next;
}
