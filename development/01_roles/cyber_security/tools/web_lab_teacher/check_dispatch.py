"""Stable Web checker command. Only explicitly supported tasks are accepted."""
import sys
sys.dont_write_bytecode = True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: jdu-web-check bootstrap|P1|M1 [--no-submit | --retry UUID]')
        raise SystemExit(2)
    if sys.argv[1] == 'bootstrap':
        from check_bootstrap import main
    elif sys.argv[1] in ('P1', 'M1'):
        from check_http import main
    else:
        print('Unsupported task; supported: bootstrap P1 M1')
        raise SystemExit(2)
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('WEB_CHECK_STOPPED=' + type(exc).__name__ + '; no readiness granted')
        raise SystemExit(2)
