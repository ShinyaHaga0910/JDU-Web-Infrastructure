-- Read-only student check: replace only the fictional item code.
SELECT code,name,quantity,location,description,is_public
 FROM public.catalog_item WHERE code='DEMO-PC-001';
