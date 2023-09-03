

-- mysql

CREATE or replace VIEW `recsys_actionlog_of_all`
AS
SELECT
   *,
   case
     when DATE_ADD(first_reach, INTERVAL 1 DAY) > create_at and isnull(uid) then "newAnonymous"
     when DATE_ADD(first_reach, INTERVAL 1 DAY) > create_at and not isnull(uid) then "newUser"
     when DATE_ADD(first_reach, INTERVAL 1 DAY) <= create_at and isnull(uid) then "oldAnonymous"
     when DATE_ADD(first_reach, INTERVAL 1 DAY) <= create_at and not isnull(uid) then "oldUser"
     when (isnull(uid) or uid = '') and (isnull(ud) or ud = '') then "anonymous"
     else "unknown"
   end as user_group,
   if(keywords is null, "noKeyword", "Keyword") as algorithm_group,
   if((`recsys_actionlog`.`action` = 1),1,0) AS `show`,
   if((`recsys_actionlog`.`action` = 2),1,0) AS `click`,
   if((author_id is null or LENGTH(TRIM(author_id)) = 0), 0, 1) AS `click_author`,
   TIME_TO_SEC(TIMEDIFF(create_at, first_reach)) AS `age`
FROM
  `recsys_actionlog`
;



CREATE or replace VIEW `recsys_actionlog_of_keywords`
AS SELECT
   *,
   if((`recsys_actionlog`.`action` = 1),1,0) AS `show`,
   if((`recsys_actionlog`.`action` = 2),1,0) AS `click`
FROM `recsys_actionlog` where keywords is not null;


CREATE or replace VIEW `recsys_actionlog_of_whole`
AS SELECT
   *,
   if((`recsys_actionlog`.`action` = 1),1,0) AS `show`,
   if((`recsys_actionlog`.`action` = 2),1,0) AS `click`
FROM `recsys_actionlog` where keywords is null;



CREATE or replace VIEW `recsys_actionlog_of_mail`
AS SELECT
   *,
   if((`recsys_actionlog`.`action` = 1),1,0) AS `show`,
   if((`recsys_actionlog`.`action` = 2),1,0) AS `click`
FROM `recsys_actionlog` where fmail is not null;


CREATE or replace VIEW `recsys_actionlog_of_wx`
AS SELECT
   *,
   if((`recsys_actionlog`.`action` = 1),1,0) AS `show`,
   if((`recsys_actionlog`.`action` = 2),1,0) AS `click`
FROM `recsys_actionlog`
where
  device = "wx";


-- select browse but not click user
select
 *
from
(
    select
      ud,
      sum(`show`) as show_count,
      sum(`click`) as click_count
    from
      recsys_actionlog_of_all
    where
      DATE(create_at) = "2021-12-19"
    group by
      ud
) t
where
  t.show_count > 4 and
  t.click_count = 0
;

-- select browse and click user

select
 *
from
(
    select
      ud,
      sum(`show`) as show_count,
      sum(`click`) as click_count
    from
      recsys_actionlog_of_all
    where
      DATE(create_at) = "2021-12-19"
    group by
      ud
) t
where
  t.click_count > 0
;

-- show every day show count statistics



select
  d, avg(show_count), std(show_count), max(show_count), min(show_count)
from

(
select
  Date(create_at) as d, ud, sum(`show`) as show_count
from
  recsys_actionlog_of_all

where
  create_at > "2022-03-01 00:00:00"

group by
  date(create_at), uid

order by
  date(create_at), sum(`show`)
) t

group by d;


-- for chart


SELECT
  d AS "time",
  sum(click_count) / sum(show_count) as ctr
FROM
  (
    select
      Date(create_at) as d,
      ud,
      sum(`show`) as show_count,
      sum(`click`) as click_count
    from
      recsys_actionlog_of_all
    where
      $__timeFilter(create_at) and
    group by
      date(create_at), ud
    order by
      date(create_at)
  ) t
where
  show_count > 6 and
  show_count < 1000
group BY
    d
ORDER BY
    d
;


-- four quadrant clean ctr
SELECT
  d AS "time",
  sum(click_count) / sum(show_count) as value,
  concat(algorithm_group, ",", user_group) as metric

FROM
  (
    select
      Date(create_at) as d,
      ud,
      sum(`show`) as show_count,
      sum(`click`) as click_count
    from
      recsys_actionlog_of_all
    where
      $__timeFilter(create_at) and
    group by
      date(create_at), ud
    order by
      date(create_at)
  ) t

WHERE
  show_count > 6 and
  show_count < 1000
group BY
  d
ORDER BY
  d asc
;



--postgresql

CREATE or replace VIEW recsys_actionlog_of_all
AS
SELECT
   *,
   case
     when first_reach + INTERVAL '1 DAY' > create_at and uid is null then 'newAnonymous'
     when first_reach + INTERVAL '1 DAY' > create_at and not uid is null then 'newUser'
     when first_reach + INTERVAL '1 DAY' <= create_at and uid is null then 'oldAnonymous'
     when first_reach + INTERVAL '1 DAY' <= create_at and not uid is null then 'oldUser'
     when (uid is null or uid = '') and (ud is null or ud = '') then 'anonymous'
     else 'unknown'
   end as user_group,
   case
     when keywords is null then 'noKeywords'
     else 'Keyword'
   end as algorithm_group,
   case
     when "action" = 1 then 1
     else 0
   end as "show",
   case
     when "action" = 2 then 1
     else 0
   end as "click",

   case
     when author_id is null or author_id = '' then 0
     else 1
   end as "click_author"
FROM
  recsys_actionlog
;


create or replace view recsys_actionlog_day_ud_stat
as
select
  "day",
  ud,
  sum("show") as "show",
  sum(click) as click
from
  recsys_actionlog_of_all
where
  ud is not null and
  length(ud) > 0
group by
  "day",
  ud
  ;

