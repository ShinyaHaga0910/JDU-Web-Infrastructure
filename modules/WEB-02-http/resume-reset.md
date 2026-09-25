# WEB-02 保存・再開・復旧の設計

## 授業終了時

学生は、使用したUbuntuの役割、変更したfile、Nginxの状態、最後に成功したHTTP確認、次回の一手を短く残します。教員が指定したLab終了操作を行います。Labを終了したときにEC2・保存領域がどう扱われるかは実機で確認してから確定します。

## 次回の開始時

教員の手順でLabを開始し、`hostnamectl`、`whoami`、対象file、`systemctl is-active nginx`、`ss -lntp`、localの`curl`を順に確認します。前回の確認結果と異なる箇所から再開します。

## 失敗時の復旧

reset対象はこの単元の配布fileとNginxの演習設定に限定します。学生のhome全体や他単元の状態を消さない方法をLab実装後に具体化します。実際のreset scriptを作る前に、対象pathを列挙し、実機で復旧と再試験を確認します。
